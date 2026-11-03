"""SS-026 §5: the generator (scripts/generate.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import generate
import inputs
import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC: dict[str, Any] = json.loads(inputs.input_path("contract").read_text("utf-8"))
KEYED = [
    "createBillingCheckout",
    "createBillingSubscriptionCheckout",
    "createGeneration",
    "createScreenshotSet",
]


def schemas_of(components: dict[str, Any]) -> str:
    spec = {"info": {"version": "9.9.9"}, "components": {"schemas": components}, "paths": {}}
    return generate.schemas_source(spec)


def run_generate(*args: str, seed: str = "0") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / "generate.py"), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
    )


def test_operations_are_sorted_and_complete() -> None:
    ops = generate.describe_operations(SPEC)
    assert list(ops) == sorted(ops)
    count = sum(
        1
        for item in SPEC["paths"].values()
        for m in generate.METHODS
        if "operationId" in item.get(m, {})
    )
    assert len(ops) == count == 58


def test_operation_traits() -> None:
    ops = generate.describe_operations(SPEC)
    assert sorted(k for k, v in ops.items() if v["idempotency_key"]) == KEYED
    upload = ops["createUpload"]
    assert upload["method"] == "POST" and upload["path"] == "/uploads"
    assert upload["body"] == "json|multipart"
    assert upload["success_statuses"] == [201]
    assert ops["getScreenshotSetArchive"]["binary"] is True
    assert ops["getGeneration"]["path_params"] == ["id"]
    assert ops["createScreenshotSet"]["response_schemas"] == ["ScreenshotSet", "ScreenshotSetQuote"]
    assert ops["createGeneration"]["request_schema"] == "CreateGenerationRequest"
    assert ops["deleteUpload"]["response_schemas"] == []


def test_duplicate_operation_id_is_an_error() -> None:
    spec = {"paths": {"/a": {"get": {"operationId": "x"}}, "/b": {"get": {"operationId": "x"}}}}
    with pytest.raises(ValueError, match="duplicate operationId x"):
        generate.describe_operations(spec)


def test_scalars_nullable_enum_array_dict() -> None:
    src = schemas_of(
        {
            "Thing": {
                "type": "object",
                "required": ["id", "tags"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "count": {"type": ["integer", "null"]},
                    "ratio": {"type": "number"},
                    "flag": {"type": "boolean"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "meta": {"type": "object", "additionalProperties": {"type": "string"}},
                    "any": {"type": "object", "additionalProperties": {}},
                    "state": {"$ref": "#/components/schemas/State"},
                },
            },
            "State": {"type": "string", "enum": ["a", "b"]},
        }
    )
    assert "class Thing(TypedDict):" in src
    assert "    id: str\n" in src
    assert "    count: NotRequired[Optional[int]]\n" in src
    assert "    ratio: NotRequired[float]\n" in src
    assert "    tags: List[str]\n" in src
    assert "    meta: NotRequired[Dict[str, str]]\n" in src
    assert "    any: NotRequired[Dict[str, Any]]\n" in src
    assert '    state: NotRequired["State"]\n' in src
    assert 'State: TypeAlias = Literal["a", "b"]\n' in src


def test_keyword_property_uses_the_functional_form() -> None:
    src = schemas_of(
        {
            "Report": {
                "type": "object",
                "required": ["from"],
                "properties": {"from": {"type": "string"}},
            }
        }
    )
    assert 'Report = TypedDict(\n    "Report",\n    {\n        "from": str,\n    },\n)\n' in src


def test_inline_objects_get_named_classes_and_collisions_get_inline() -> None:
    size = {"type": "object", "properties": {"w": {"type": "integer"}}}
    src = schemas_of(
        {"Gen": {"type": "object", "properties": {"size": size}}, "GenSize": {"type": "string"}}
    )
    assert "class GenSizeInline(TypedDict):" in src
    assert '    size: NotRequired["GenSizeInline"]\n' in src


def test_allof_ref_and_anyof() -> None:
    ref_b = {"$ref": "#/components/schemas/B"}
    src = schemas_of(
        {
            "A": {"type": "object", "properties": {"x": {"allOf": [ref_b, {"description": "d"}]}}},
            "B": {
                "anyOf": [
                    {"type": "boolean"},
                    {"type": "object", "properties": {"y": {"type": "string"}}},
                ]
            },
        }
    )
    assert '    x: NotRequired["B"]\n' in src
    assert 'B: TypeAlias = Union[bool, "BVariant2"]\n' in src
    assert "class BVariant2(TypedDict):" in src


def test_allof_extension_is_merged_and_extension_wins() -> None:
    src = schemas_of(
        {
            "Base": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "string"}, "secret": {"type": "integer"}},
            },
            "WithSecret": {
                "allOf": [
                    {"$ref": "#/components/schemas/Base"},
                    {
                        "type": "object",
                        "properties": {"secret": {"type": "string"}},
                        "required": ["secret"],
                    },
                ]
            },
        }
    )
    block = src.split("class WithSecret(TypedDict):\n", 1)[1].split("\n\n", 1)[0]
    assert block == "    id: str\n    secret: str"


def test_nullable_object_component_refs_are_optional() -> None:
    src = schemas_of(
        {
            "Sub": {"type": ["object", "null"], "properties": {"a": {"type": "string"}}},
            "State": {
                "type": "object",
                "required": ["sub"],
                "properties": {"sub": {"$ref": "#/components/schemas/Sub"}},
            },
        }
    )
    assert "class Sub(TypedDict):" in src
    assert '    sub: Optional["Sub"]\n' in src


def test_boolean_and_nullable_enums() -> None:
    props = {
        "dry": {"type": "boolean", "enum": [True]},
        "mode": {"type": ["string", "null"], "enum": ["x", None]},
    }
    src = schemas_of({"Q": {"type": "object", "required": ["dry", "mode"], "properties": props}})
    assert "    dry: Literal[True]\n" in src
    assert '    mode: Optional[Literal["x"]]\n' in src


@pytest.mark.parametrize(
    "bad", [{"oneOf": [{"type": "string"}]}, {"type": "string", "const": "x"}, {"not": {}}]
)
def test_unknown_constructs_fail_loudly(bad: dict[str, Any]) -> None:
    with pytest.raises(generate.UnsupportedSchema, match="X"):
        schemas_of({"X": {"type": "object", "properties": {"p": bad}}})


def test_the_real_contract_generates() -> None:
    src = generate.schemas_source(SPEC)
    compile(src, "schemas.py", "exec")
    assert "UsageReport = TypedDict(" in src  # `from` is a Python keyword
    assert "class Generation(TypedDict):" in src
    assert "WebhookEvent: TypeAlias = Union[" in src
    assert "class ListGenerationsQuery(TypedDict, total=False):" in src
    assert "GetUsageQuery = TypedDict(" in src


def test_operations_source() -> None:
    src = generate.operations_source(SPEC)
    assert f"CONTRACT_VERSION: Final = {json.dumps(SPEC['info']['version'])}" in src
    assert '    "createGeneration": Operation(\n' in src
    assert "OperationId: TypeAlias = Literal[" in src


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_check_passes_on_the_committed_files_with_any_hash_seed(seed: str) -> None:
    result = run_generate("--check", seed=seed)
    assert result.returncode == 0, result.stderr


def test_check_fails_on_stale_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate, "OUT", tmp_path)
    (tmp_path / "schemas.py").write_text("stale\n", "utf-8")
    assert generate.main(["--check"]) == 1


def test_print_operations_is_json() -> None:
    result = run_generate("--print-operations")
    assert json.loads(result.stdout)["getMe"]["method"] == "GET"
