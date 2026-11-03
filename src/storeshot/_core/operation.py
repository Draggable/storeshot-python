"""One API operation's method, path and request traits (SS-026 §5; generated in operations.py)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    tag: str | None
    idempotency_key: bool
    wait: bool
    path_params: tuple[str, ...]
    query_params: tuple[str, ...]
    body: str
    success_statuses: tuple[int, ...]
    binary: bool
    #: Component name of the JSON request body, if any.
    request_schema: str | None
    #: Component names a 2xx JSON answer may have (anyOf flattened), sorted.
    response_schemas: tuple[str, ...]
