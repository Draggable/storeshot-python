"""The request loop (SS-026 §6.1–6.3), against Requester directly."""

from __future__ import annotations

import json

import httpx
import pytest
from _mock import BASE, TEST_KEY, MockApi

from storeshot._core.request import OAuthError, Requester, RequesterConfig, ResponseMeta
from storeshot._errors import StoreshotConnectionError, StoreshotError, StoreshotTimeoutError


def requester(
    api: MockApi, *, key: str | None = TEST_KEY, metas: list[ResponseMeta] | None = None
) -> Requester:
    return Requester(
        RequesterConfig(
            api_key=key,
            base_url=BASE,
            http=api.http(),
            timeout=60.0,
            max_retries=2,
            max_retry_after=60.0,
            client_header="api/test@1",
            user_agent="storeshot-sdk-python/test",
            default_headers={"X-Default": "d"},
            on_response=None if metas is None else metas.append,
        )
    )


def error(code: str, status: int, headers: dict[str, str] | None = None) -> object:
    body = {"error": {"code": code, "message": code.lower()}}
    return lambda _r: httpx.Response(status, json=body, headers=headers)


def test_headers_query_and_json(api: MockApi) -> None:
    api.json("GET", "/generations", {"data": [], "nextCursor": None})
    r = requester(api)
    r.call(
        "listGenerations",
        query={"limit": 5, "cursor": None, "metadata": "campaign:spring", "x": True},
        options={"request_id": "abc", "headers": {"X-Trace": "1"}},
    )
    req = api.requests[-1]
    assert str(req.url) == f"{BASE}/generations?limit=5&metadata=campaign%3Aspring&x=true"
    assert req.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert req.headers["x-storeshot-client"] == "api/test@1"
    assert req.headers["user-agent"] == "storeshot-sdk-python/test"
    assert req.headers["x-request-id"] == "abc"
    assert req.headers["x-trace"] == "1" and req.headers["x-default"] == "d"
    assert req.headers["accept"] == "application/json"
    assert "idempotency-key" not in req.headers and "content-type" not in req.headers


def test_path_parameters_are_encoded_and_required(api: MockApi) -> None:
    api.json("GET", "/generations/a%2Fb", {"id": "a/b"})
    assert requester(api).call("getGeneration", path={"id": "a/b"}) == {"id": "a/b"}
    assert api.requests[-1].url.raw_path == b"/v1/generations/a%2Fb"
    with pytest.raises(StoreshotError, match='missing path parameter "id"'):
        requester(api).call("getGeneration", path={})


def test_json_body_and_prefer_wait(api: MockApi) -> None:
    api.json("POST", "/generations", {"id": "g1"}, status=202)
    requester(api).call("createGeneration", json={"inputs": ["é"]}, wait=12.7)
    req = api.requests[-1]
    assert req.headers["content-type"] == "application/json"
    assert req.headers["prefer"] == "wait=12"
    assert json.loads(req.content) == {"inputs": ["é"]}


def test_auto_idempotency_key_is_reused_across_retries(api: MockApi) -> None:
    api.on(
        "POST",
        "/generations",
        error("INTERNAL_ERROR", 500),
        lambda _r: httpx.Response(202, json={"id": "g1"}),
    )
    assert requester(api).call("createGeneration", json={"inputs": []}) == {"id": "g1"}
    keys = {r.headers["idempotency-key"] for r in api.requests}
    assert len(api.requests) == 2 and len(keys) == 1


def test_given_idempotency_key_is_used_and_validated(api: MockApi) -> None:
    api.json("POST", "/generations", {"id": "g1"}, status=202)
    requester(api).call("createGeneration", json={}, idempotency_key="release-2.4")
    assert api.requests[-1].headers["idempotency-key"] == "release-2.4"
    for bad in ("x" * 256, "", "a\nb"):
        with pytest.raises(StoreshotError, match="idempotency_key"):
            requester(api).call("createGeneration", json={}, idempotency_key=bad)


def test_read_only_post_has_no_key_and_is_retried(api: MockApi) -> None:
    api.on(
        "POST",
        "/screenshot-sets",
        error("INTERNAL_ERROR", 502),
        lambda _r: httpx.Response(200, json={"dryRun": True}),
    )
    result = requester(api).call(
        "createScreenshotSet", json={}, query={"dryRun": "true"}, read_only=True
    )
    assert result == {"dryRun": True}
    assert all("idempotency-key" not in r.headers for r in api.requests)


def test_unsafe_post_is_not_retried_and_says_so(api: MockApi) -> None:
    api.on("POST", "/uploads", httpx.ConnectError("boom"))
    with pytest.raises(StoreshotConnectionError) as info:
        requester(api).call("createUpload", json={"url": "https://example.com/a.png"})
    assert "may have reached the server" in info.value.message
    assert isinstance(info.value.__cause__, httpx.ConnectError)
    assert len(api.requests) == 1


def test_refusals_are_retried_for_unsafe_posts(api: MockApi, fake_clock: object) -> None:
    api.on(
        "POST",
        "/uploads",
        error("RATE_LIMITED", 429, {"retry-after": "2"}),
        lambda _r: httpx.Response(201, json={"id": "u1"}),
    )
    assert requester(api).call("createUpload", json={"url": "https://example.com/a.png"}) == {
        "id": "u1"
    }
    assert fake_clock.sleeps == [2.1]  # type: ignore[attr-defined]


def test_long_retry_after_is_not_waited_for(api: MockApi) -> None:
    api.on("GET", "/me", error("RATE_LIMITED", 429, {"retry-after": "3600"}))
    with pytest.raises(StoreshotError) as info:
        requester(api).call("getMe")
    assert info.value.retry_after_seconds == 3600 and len(api.requests) == 1


def test_timeouts_map_to_timeout_errors_and_are_retried_for_get(api: MockApi) -> None:
    api.on("GET", "/me", httpx.ReadTimeout("slow"))
    with pytest.raises(StoreshotTimeoutError) as info:
        requester(api).call("getMe")
    assert info.value.code == "TIMEOUT" and len(api.requests) == 3


def test_per_call_max_retries(api: MockApi) -> None:
    api.on("GET", "/me", httpx.ReadTimeout("slow"))
    with pytest.raises(StoreshotTimeoutError):
        requester(api).call("getMe", options={"max_retries": 0})
    assert len(api.requests) == 1


def test_204_and_empty_bodies_are_none(api: MockApi) -> None:
    api.on("DELETE", "/uploads/u1", lambda _r: httpx.Response(204))
    assert requester(api).call("deleteUpload", path={"id": "u1"}) is None


def test_bad_json_is_unexpected_response(api: MockApi) -> None:
    api.on("GET", "/me", lambda _r: httpx.Response(200, text="<html>"))
    with pytest.raises(StoreshotError) as info:
        requester(api).call("getMe")
    assert info.value.code == "UNEXPECTED_RESPONSE"


def test_on_response_meta(api: MockApi) -> None:
    metas: list[ResponseMeta] = []
    seen: list[ResponseMeta] = []
    headers = {"x-request-id": "r1", "ratelimit": "limit=60", "idempotent-replayed": "true"}
    api.json("GET", "/me", {}, headers=headers)
    requester(api, metas=metas).call("getMe", options={"on_response": seen.append})
    assert metas == seen and metas[0].operation_id == "getMe" and metas[0].request_id == "r1"
    assert metas[0].rate_limit == "limit=60" and metas[0].idempotent_replayed is True
    assert metas[0].attempt == 0


def test_key_less_client_only_calls_anonymous_operations(api: MockApi) -> None:
    api.json("POST", "/auth/device", {"device_code": "d"})
    r = requester(api, key=None)
    assert r.call("createDeviceAuthorization", anonymous=True, json={}) == {"device_code": "d"}
    assert "authorization" not in api.requests[-1].headers
    with pytest.raises(StoreshotError) as info:
        r.call("getMe")
    assert info.value.code == "MISSING_API_KEY"


def test_anonymous_operations_never_send_the_key(api: MockApi) -> None:
    api.json("POST", "/auth/device", {"device_code": "d"})
    requester(api).call("createDeviceAuthorization", anonymous=True, json={})
    assert "authorization" not in api.requests[-1].headers


def test_oauth_error_passthrough(api: MockApi) -> None:
    api.json("POST", "/auth/device/token", {"error": "authorization_pending"}, status=400)
    result = requester(api, key=None).call(
        "createDeviceToken", anonymous=True, oauth_errors=True, json={}
    )
    assert result == OAuthError(error="authorization_pending", error_description=None)


def test_redirects_are_not_followed(api: MockApi) -> None:
    api.on("GET", "/me", lambda _r: httpx.Response(302, headers={"location": "https://evil.test/"}))
    with pytest.raises(StoreshotError) as info:
        requester(api).call("getMe")
    assert info.value.status == 302 and len(api.requests) == 1


def test_key_never_appears_in_errors(api: MockApi) -> None:
    api.json(
        "GET", "/me", {"error": {"code": "AUTH_INVALID", "message": f"bad {TEST_KEY}"}}, status=401
    )
    with pytest.raises(StoreshotError) as info:
        requester(api).call("getMe")
    assert TEST_KEY not in str(info.value) and TEST_KEY not in repr(info.value)
