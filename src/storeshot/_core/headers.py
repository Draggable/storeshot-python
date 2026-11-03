"""Header and credential rules shared with the server and the TS SDK (SS-026 §6.1, §7.2)."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .._errors import StoreshotError
from .._version import __version__
from .options import ClientIdentity

#: Same rule as the server (v1/attribution.ts); an invalid header would be ignored there.
CLIENT_HEADER_PATTERN = re.compile(r"(?:api|web|mcp|cli)/[A-Za-z0-9._@+-]{1,100}", re.ASCII)
#: Same rule as the server's request-id middleware.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9_\-=]{1,128}", re.ASCII)
IDEMPOTENCY_KEY_PATTERN = re.compile(r"[\x20-\x7e]{1,255}")
CREDENTIAL_PATTERN = re.compile(r"[\x21-\x7e]+")
HEADER_VALUE_PATTERN = re.compile(r"[\t\x20-\x7e]*")
#: Headers the SDK owns; default and per-call headers may not set them.
RESERVED_HEADERS = ("authorization", "x-storeshot-client", "idempotency-key")


def invalid(message: str) -> StoreshotError:
    return StoreshotError("INVALID_CONFIGURATION", message)


def default_client_name() -> str:
    return f"storeshot-sdk-python@{__version__}"


def client_header(identity: ClientIdentity | None) -> str:
    """The X-Storeshot-Client value, validated so the server never silently drops it."""
    identity = identity or {}
    value = f"{identity.get('surface', 'api')}/{identity.get('name', default_client_name())}"
    if not CLIENT_HEADER_PATTERN.fullmatch(value):
        raise invalid(
            f'Invalid client identity "{value}": surface api|web|mcp|cli, name of 1–100 '
            "characters A-Z a-z 0-9 . _ @ + -."
        )
    return value


def assert_credential(value: str) -> None:
    """Credentials: printable ASCII without spaces (no header injection, no stray newline)."""
    if not CREDENTIAL_PATTERN.fullmatch(value):
        raise invalid("The API key contains whitespace or non-printable characters.")


def assert_header_value(name: str, value: str) -> None:
    if not HEADER_VALUE_PATTERN.fullmatch(value):
        raise invalid(f"Header {name} has a line break or a non-ASCII character.")


def assert_request_id(value: str) -> None:
    if not REQUEST_ID_PATTERN.fullmatch(value):
        raise invalid("request_id must be 1–128 characters of A-Z a-z 0-9 _ - =.")


def user_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Validates user-supplied headers and refuses the ones the SDK owns."""
    out: dict[str, str] = {}
    for name, value in (headers or {}).items():
        if name.lower() in RESERVED_HEADERS:
            raise invalid(f"Header {name} is set by the SDK; use the matching option instead.")
        assert_header_value(name, value)
        out[name] = value
    return out
