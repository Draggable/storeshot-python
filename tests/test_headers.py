from __future__ import annotations

from typing import Any

import pytest

from storeshot import __version__
from storeshot._core.headers import (
    assert_credential,
    assert_request_id,
    client_header,
    user_headers,
)
from storeshot._errors import StoreshotError


def test_default_client_header() -> None:
    assert client_header(None) == f"api/storeshot-sdk-python@{__version__}"
    assert client_header({"surface": "cli", "name": "my-tool@1.0"}) == "cli/my-tool@1.0"


@pytest.mark.parametrize(
    "identity", [{"surface": "bot"}, {"name": "has space"}, {"name": "x" * 101}, {"name": "ok\n"}]
)
def test_invalid_client_identity(identity: Any) -> None:
    with pytest.raises(StoreshotError) as info:
        client_header(identity)
    assert info.value.code == "INVALID_CONFIGURATION"


@pytest.mark.parametrize("key", ["ss_test_x y", "ss_test_x\n", "ss_test_é", ""])
def test_credentials_must_be_printable_ascii(key: str) -> None:
    with pytest.raises(StoreshotError):
        assert_credential(key)


def test_request_id_rule() -> None:
    assert_request_id("abc_DEF-123=")
    for bad in ("", "a" * 129, "a b", "abc\n"):
        with pytest.raises(StoreshotError):
            assert_request_id(bad)


def test_user_headers_refuse_reserved_and_line_breaks() -> None:
    assert user_headers({"X-Trace": "1"}) == {"X-Trace": "1"}
    for name in ("Authorization", "x-storeshot-client", "Idempotency-Key"):
        with pytest.raises(StoreshotError):
            user_headers({name: "v"})
    with pytest.raises(StoreshotError):
        user_headers({"X-Bad": "a\r\nb"})
