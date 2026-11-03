"""SS-026 §10.1: every operation is covered, and the models match the contract."""

from __future__ import annotations

import json
import re
import types
from typing import Any, Union, get_args, get_origin

import httpx
import inputs
import pytest
from _calls import OPERATION_CALLS
from _mock import MockApi
from _shape import check

import storeshot.types as T
from storeshot._compat import get_type_hints, is_typeddict
from storeshot._generated.operations import OPERATIONS
from storeshot._operation_map import EXTRA_METHODS, OPERATION_MAP, PYTHON_ONLY_METHODS
from storeshot._resources.screenshot_sets import ArchiveLayout

SPEC: dict[str, Any] = json.loads(inputs.input_path("contract").read_text("utf-8"))
COMPONENTS: dict[str, Any] = SPEC["components"]["schemas"]
SDK_SHAPED = {"createDeviceAuthorization", "createDeviceToken"}  # return SDK dataclasses
KEYED = {oid for oid, op in OPERATIONS.items() if op.idempotency_key}
ANONYMOUS = {"createDeviceAuthorization", "createDeviceToken"}


def resolve(client: Any, method_path: str) -> Any:
    target = client
    for part in method_path.split("."):
        target = getattr(target, part)
    return target


def names_of(hint: Any) -> set[str]:
    if is_typeddict(hint):
        return {hint.__name__}
    if get_origin(hint) in (Union, types.UnionType):  # `X | None` is types.UnionType before 3.14
        return {n for a in get_args(hint) for n in names_of(a)}
    return set()


def object_schema(name: str) -> dict[str, Any]:
    """The component as one object (allOf extensions merged, like the generator does)."""
    schema = COMPONENTS[name]
    if "allOf" not in schema:
        return schema
    base = object_schema(schema["allOf"][0]["$ref"].rsplit("/", 1)[1])
    properties = dict(base["properties"])
    required = set(base.get("required", []))
    for part in schema["allOf"][1:]:
        properties.update(part.get("properties", {}))
        required |= set(part.get("required", []))
    return {"properties": properties, "required": sorted(required)}


def test_every_operation_is_mapped_and_called(api: MockApi) -> None:
    assert set(OPERATION_MAP) == set(OPERATIONS)
    assert set(OPERATION_CALLS) == set(OPERATIONS)
    client = api.client()
    for path in [*OPERATION_MAP.values(), *EXTRA_METHODS, *PYTHON_ONLY_METHODS]:
        assert callable(resolve(client, path)), path
    for oid in [*EXTRA_METHODS.values(), *PYTHON_ONLY_METHODS.values()]:
        assert oid in OPERATIONS


def test_method_types_match_the_contract(api: MockApi) -> None:
    client = api.client()
    checked = 0
    for oid, path in OPERATION_MAP.items():
        op = OPERATIONS[oid]
        hints = get_type_hints(resolve(client, path))
        if oid not in SDK_SHAPED and op.response_schemas and not op.binary:
            returned = names_of(hints["return"])
            assert returned and returned <= set(op.response_schemas), oid
            checked += 1
        if "body" in hints and op.request_schema:
            assert names_of(hints["body"]) == {op.request_schema}, oid
    assert checked >= 45


def test_archive_layout_matches_the_contract() -> None:
    query = get_type_hints(T.GetScreenshotSetArchiveQuery)["layout"]
    assert set(get_args(query)) == set(get_args(ArchiveLayout))


OBJECT_COMPONENTS = sorted(
    n for n, s in COMPONENTS.items() if ("properties" in s or "allOf" in s) and "anyOf" not in s
)


@pytest.mark.parametrize("name", OBJECT_COMPONENTS)
def test_object_schemas_have_the_contract_keys(name: str) -> None:
    schema, generated = object_schema(name), getattr(T, name)
    if not is_typeddict(generated):  # allOf of one $ref plus annotations is an alias
        return
    assert set(get_type_hints(generated)) == set(schema["properties"]), name
    assert set(generated.__required_keys__) == set(schema.get("required", [])), name


@pytest.mark.parametrize("name", sorted(n for n, s in COMPONENTS.items() if "enum" in s))
def test_enum_schemas_are_literals(name: str) -> None:
    values = [v for v in COMPONENTS[name]["enum"] if v is not None]
    args = [a for a in get_args(getattr(T, name)) if a is not type(None)]
    flat = [x for a in args for x in (get_args(a) or [a])]
    assert flat == values, name


def instance(schema: dict[str, Any], full: bool, depth: int = 0) -> Any:
    """A minimal (required keys) or full (every key) value of a JSON schema."""
    if "$ref" in schema:
        return instance(object_schema(schema["$ref"].rsplit("/", 1)[1]), full, depth + 1)
    if "allOf" in schema:
        ref = next(p for p in schema["allOf"] if "$ref" in p)
        others = [p for p in schema["allOf"] if "$ref" not in p and "properties" in p]
        if not others:
            return instance(ref, full, depth + 1)
        merged = object_schema(ref["$ref"].rsplit("/", 1)[1])
        props = {
            **merged["properties"],
            **{k: v for p in others for k, v in p["properties"].items()},
        }
        required = set(merged.get("required", [])) | {
            r for p in others for r in p.get("required", [])
        }
        return instance({"properties": props, "required": sorted(required)}, full, depth + 1)
    if "anyOf" in schema:
        return instance(schema["anyOf"][-1 if full else 0], full, depth + 1)
    if "enum" in schema:
        return next(v for v in schema["enum"] if v is not None)
    kinds = schema.get("type")
    kind = next((k for k in (kinds if isinstance(kinds, list) else [kinds]) if k != "null"), None)
    if kind == "object" or "properties" in schema:
        props = schema.get("properties", {})
        keys = props if full and depth < 6 else schema.get("required", [])
        return {k: instance(props[k], full, depth + 1) for k in keys}
    if kind == "array":
        return [instance(schema["items"], full, depth + 1)] if full and depth < 6 else []
    return {"string": "x", "integer": 1, "number": 1.5, "boolean": True}.get(kind or "")


RESPONSES = sorted({n for op in OPERATIONS.values() for n in op.response_schemas})


@pytest.mark.parametrize("full", [False, True], ids=["minimal", "full"])
@pytest.mark.parametrize("name", RESPONSES)
def test_response_schemas_round_trip(name: str, full: bool) -> None:
    value = instance(object_schema(name), full)
    assert check(value, getattr(T, name)) == []
    assert json.loads(json.dumps(value)) == value


@pytest.mark.parametrize("name", RESPONSES)
def test_wrong_values_are_caught(name: str) -> None:
    value = instance(object_schema(name), True)
    assert check({**value, "__unknown__": 1}, getattr(T, name)) != []


def test_every_operation_sends_its_method_path_and_headers(api: MockApi) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/archive"):
            return httpx.Response(200, content=b"PK")
        if request.url.path.endswith("/auth/device"):
            device = {
                "device_code": "d",
                "user_code": "u",
                "verification_uri": "v",
                "verification_uri_complete": "w",
                "expires_in": 600,
                "interval": 5,
            }
            return httpx.Response(200, json=device)
        if request.url.path.endswith("/auth/device/token"):
            return httpx.Response(400, json={"error": "authorization_pending"})
        return httpx.Response(200, json={})

    api.fallback = answer
    client = api.client()
    for oid, call in OPERATION_CALLS.items():
        call(client)
        request, op = api.requests[-1], OPERATIONS[oid]
        pattern = "/v1" + re.sub(r"\{[^}]+\}", "[^/]+", op.path)
        assert request.method == op.method and re.fullmatch(pattern, request.url.path), oid
        assert ("idempotency-key" in request.headers) == (oid in KEYED), oid
        assert ("authorization" in request.headers) == (oid not in ANONYMOUS), oid
    assert len(api.requests) == len(OPERATIONS)
