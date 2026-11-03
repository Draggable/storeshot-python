"""Client options, the base URL rule and the key guards (SS-026 §4.1, §7.2, §7.3)."""

from __future__ import annotations

import sys
from typing import Any

import httpx
import pytest
from _mock import BASE, LIVE_KEY, TEST_KEY, MockApi

from storeshot import Storeshot
from storeshot._errors import StoreshotError


def test_reads_the_key_and_base_url_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, api: MockApi
) -> None:
    monkeypatch.setenv("STORESHOT_API_KEY", TEST_KEY)
    monkeypatch.setenv("STORESHOT_BASE_URL", "http://127.0.0.1:3001/v1/")
    client = Storeshot(http_client=api.http())
    assert client.base_url == "http://127.0.0.1:3001/v1"
    assert client.environment == "test"


def test_default_base_url() -> None:
    assert Storeshot(TEST_KEY).base_url == "https://api.storeshot.art/v1"


def test_missing_key() -> None:
    with pytest.raises(StoreshotError) as info:
        Storeshot()
    assert info.value.code == "MISSING_API_KEY" and "console.storeshot.art" in info.value.message
    with pytest.raises(StoreshotError):
        Storeshot("")


@pytest.mark.parametrize(
    "url",
    [
        "https://api.storeshot.art/v1",
        "http://localhost:3001/v1",
        "http://127.0.0.1/v1",
        "http://[::1]:8080/v1",
    ],
)
def test_accepted_base_urls(url: str) -> None:
    assert Storeshot(TEST_KEY, base_url=url).base_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.storeshot.art/v1",
        "ftp://x/v1",
        "https://u:p@x/v1",
        "https://x/v1?a=1",
        "https://x/v1#f",
        "/v1",
        "http://127.0.0.1.evil.test/v1",
        "https://x:notaport/v1",
    ],
)
def test_refused_base_urls(url: str) -> None:
    with pytest.raises(StoreshotError) as info:
        Storeshot(TEST_KEY, base_url=url)
    assert info.value.code == "INVALID_CONFIGURATION"


def test_environment_guard() -> None:
    assert Storeshot(TEST_KEY, environment="test").environment == "test"
    assert Storeshot(LIVE_KEY, environment="live").environment == "live"
    jwt = "eyJhbGciOiJIUzI1NiJ9.e30.x"
    for key, env in ((LIVE_KEY, "test"), (TEST_KEY, "live"), (jwt, "test"), (None, "test")):
        with pytest.raises(StoreshotError) as info:
            Storeshot(key, environment=env)  # type: ignore[arg-type]
        assert info.value.code == "INVALID_CONFIGURATION"
        assert LIVE_KEY not in info.value.message and TEST_KEY not in info.value.message
    assert Storeshot(jwt).environment is None


def test_browser_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "emscripten")
    with pytest.raises(StoreshotError) as info:
        Storeshot(TEST_KEY)
    assert info.value.code == "BROWSER_NOT_ALLOWED"
    Storeshot(TEST_KEY, dangerously_allow_browser=True)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("timeout", -1),
        ("max_retries", 11),
        ("max_retry_after", float("inf")),
        ("timeout", True),
        ("timeout", "60"),
    ],
)
def test_number_options(name: str, value: Any) -> None:
    with pytest.raises(StoreshotError):
        Storeshot(TEST_KEY, **{name: value})


def test_invalid_key_and_headers() -> None:
    with pytest.raises(StoreshotError):
        Storeshot("ss_test_has space")
    with pytest.raises(StoreshotError):
        Storeshot(TEST_KEY, default_headers={"Authorization": "x"})
    with pytest.raises(StoreshotError):
        Storeshot(TEST_KEY, client_identity={"surface": "bot"})  # type: ignore[typeddict-item]


def test_repr_masks_the_key() -> None:
    client = Storeshot(TEST_KEY)
    assert repr(client) == "Storeshot(base_url=https://api.storeshot.art/v1, api_key=ss_test_…)"
    assert str(client) == repr(client)
    assert TEST_KEY not in repr(client._requester._auth)
    assert repr(Storeshot(None)).endswith("api_key=none)")


def test_me_health_status_and_headers(api: MockApi) -> None:
    api.json("GET", "/me", {"user": {"id": "u"}})
    api.json("GET", "/health", {"status": "ok"})
    api.json("GET", "/status", {"status": "operational"})
    client = api.client(client_identity={"surface": "cli", "name": "my-tool@1.0"})
    assert client.me() == {"user": {"id": "u"}}
    assert client.health()["status"] == "ok"
    assert client.status()["status"] == "operational"
    assert api.requests[0].headers["user-agent"].startswith("storeshot-sdk-python/")
    assert api.requests[0].headers["x-storeshot-client"] == "cli/my-tool@1.0"


def test_key_less_client(api: MockApi) -> None:
    client = api.client(api_key=None)
    with pytest.raises(StoreshotError) as info:
        client.me()
    assert info.value.code == "MISSING_API_KEY" and api.requests == []


def test_context_manager_closes_only_its_own_http_client(api: MockApi) -> None:
    http = api.http()
    with Storeshot(TEST_KEY, base_url=BASE, http_client=http):
        pass
    assert not http.is_closed
    with Storeshot(TEST_KEY) as own:
        inner: httpx.Client = own._http
    assert inner.is_closed
