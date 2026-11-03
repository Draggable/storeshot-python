"""Per-call options and the client identity (SS-026 §4.1)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Literal

from .._compat import TypedDict

if TYPE_CHECKING:
    from .request import ResponseMeta


class RequestOptions(TypedDict, total=False):
    """Keyword options every method accepts."""

    timeout: float
    """Seconds per network operation of each attempt (overrides the client's)."""
    max_retries: int
    request_id: str
    """Sent as X-Request-Id (1–128 of A-Z a-z 0-9 _ - =) to correlate with your logs."""
    headers: Mapping[str, str]
    on_response: Callable[[ResponseMeta], None]


class ClientIdentity(TypedDict, total=False):
    """X-Storeshot-Client: `api` by default; `cli`/`mcp` for such tools (usage labels)."""

    surface: Literal["api", "web", "mcp", "cli"]
    name: str
    """1–100 of A-Z a-z 0-9 . _ @ + -, for example `my-tool@1.2.0`."""
