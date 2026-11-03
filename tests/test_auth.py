"""Device authorization (SS-026 §6.7)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from _mock import TEST_KEY, MockApi

from storeshot._errors import StoreshotError

STARTED = {
    "device_code": "D" * 43,
    "user_code": "BCDF-GHJK",
    "verification_uri": "https://console.storeshot.art/device",
    "verification_uri_complete": "https://console.storeshot.art/device?code=BCDF-GHJK",
    "expires_in": 600,
    "interval": 5,
}
TOKEN = {
    "access_token": TEST_KEY,
    "token_type": "bearer",
    "key_id": "k1",
    "scope": "usage:read generations:read",
    "environment": "test",
}


def oauth(error: str, headers: dict[str, str] | None = None) -> Any:
    return lambda _r: httpx.Response(400, json={"error": error}, headers=headers)


def test_link_account_follows_rfc_8628(api: MockApi, fake_clock: Any) -> None:
    api.json("POST", "/auth/device", STARTED)
    api.on(
        "POST",
        "/auth/device/token",
        oauth("authorization_pending"),
        oauth("slow_down", {"retry-after": "12"}),
        lambda _r: httpx.Response(200, json=TOKEN),
    )
    shown: list[Any] = []
    client = api.client(api_key=None)
    linked = client.auth.link_account(client_name="tool", environment="test", on_code=shown.append)
    assert linked.key_id == "k1" and linked.scopes == ("usage:read", "generations:read")
    assert linked.api_key == TEST_KEY and TEST_KEY not in repr(linked)
    assert fake_clock.sleeps == [5, 5, 12]
    assert json.loads(api.requests[0].content) == {"client_name": "tool", "environment": "test"}
    assert json.loads(api.requests[1].content)["device_code"] == "D" * 43
    assert all("authorization" not in r.headers for r in api.requests)
    assert shown[0].user_code == "BCDF-GHJK" and not hasattr(shown[0], "device_code")


def test_scopes_are_joined(api: MockApi) -> None:
    api.json("POST", "/auth/device", STARTED)
    code = api.client(api_key=None).auth.start_device_authorization(scopes=["a:b", "c:d"])
    assert json.loads(api.requests[0].content) == {"scope": "a:b c:d"}
    assert "D" * 43 not in repr(code)


def test_link_account_expires(api: MockApi) -> None:
    api.json("POST", "/auth/device", {**STARTED, "expires_in": 9})
    api.on("POST", "/auth/device/token", oauth("authorization_pending"))
    with pytest.raises(StoreshotError) as info:
        api.client(api_key=None).auth.link_account(on_code=lambda _c: None)
    assert info.value.code == "DEVICE_CODE_EXPIRED"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        ("access_denied", "DEVICE_ACCESS_DENIED"),
        ("expired_token", "DEVICE_CODE_EXPIRED"),
        ("invalid_grant", "DEVICE_INVALID_GRANT"),
        ("weird", "UNEXPECTED_RESPONSE"),
    ],
)
def test_terminal_poll_errors(api: MockApi, error: str, code: str) -> None:
    api.on("POST", "/auth/device/token", oauth(error))
    with pytest.raises(StoreshotError) as info:
        api.client(api_key=None).auth.poll_device_token("D" * 43)
    assert info.value.code == code and info.value.details == {"error": error}
