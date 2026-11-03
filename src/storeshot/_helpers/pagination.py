"""Cursor pagination (SS-026 §6.6; Python only, TS follow-up F2)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

from .._errors import StoreshotError


def paginate(
    fetch: Callable[[dict[str, Any]], Mapping[str, Any]], query: Mapping[str, Any] | None
) -> Iterator[Any]:
    """Yields every item of every page, fetching the next page only when it is needed."""
    params = dict(query or {})
    seen: set[str] = set()
    while True:
        page = fetch(dict(params))
        yield from page["data"]
        cursor = page.get("nextCursor")
        if cursor is None:
            return
        if cursor in seen:
            raise StoreshotError(
                "UNEXPECTED_RESPONSE",
                f"The API returned the cursor {cursor!r} twice; stopping to avoid an endless loop.",
            )
        seen.add(cursor)
        params["cursor"] = cursor
