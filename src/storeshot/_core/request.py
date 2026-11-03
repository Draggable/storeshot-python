"""The one synchronous I/O loop (SS-026 §6.1): build, send, parse, decide, retry."""

from __future__ import annotations

import json as _json
import math
import re
import uuid
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import httpx

from .._errors import (
    StoreshotConnectionError,
    StoreshotError,
    StoreshotTimeoutError,
    error_from_response,
)
from .._generated.operations import OPERATIONS
from . import clock
from .headers import IDEMPOTENCY_KEY_PATTERN, assert_header_value, assert_request_id, user_headers
from .options import RequestOptions
from .retry import AttemptOutcome, decide_retry, parse_retry_after

#: POSTs that compute without storing anything, so repeating one is harmless.
READ_ONLY_POSTS: Mapping[str, str] = {
    "createPalette": "computes a palette; stores nothing, charges nothing (SS-008)",
}
MAYBE_PROCESSED = " The request may have reached the server; check before repeating it."
_UNSET: Any = object()


@dataclass(frozen=True)
class ResponseMeta:
    """What every response (each attempt) reports to on_response."""

    operation_id: str
    status: int
    #: 0 for the first attempt.
    attempt: int
    request_id: str | None
    #: Idempotent-Replayed: true (None when the header is absent).
    idempotent_replayed: bool | None
    rate_limit: str | None
    rate_limit_policy: str | None
    retry_after_seconds: int | None
    headers: httpx.Headers


@dataclass(frozen=True)
class OAuthError:
    """An RFC 6749 §5.2 error body (the device token endpoint's 400s)."""

    error: str
    error_description: str | None


@dataclass(frozen=True)
class RequesterConfig:
    api_key: str | None
    base_url: str
    http: httpx.Client
    timeout: float
    max_retries: int
    max_retry_after: float
    client_header: str
    user_agent: str
    default_headers: Mapping[str, str]
    on_response: Callable[[ResponseMeta], None] | None


class _BearerAuth(httpx.Auth):
    """Adds the key at send time, so no SDK frame holds a headers dict with it (§7.1)."""

    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request

    def __repr__(self) -> str:
        return "_BearerAuth(…)"


def build_url(
    base_url: str,
    operation_id: str,
    path: Mapping[str, str] | None,
    query: Mapping[str, Any] | None,
) -> str:
    template = OPERATIONS[operation_id].path

    def fill(match: re.Match[str]) -> str:
        value = (path or {}).get(match.group(1))
        if value is None or value == "":
            raise StoreshotError(
                "INVALID_CONFIGURATION",
                f'{operation_id}: missing path parameter "{match.group(1)}".',
                operation_id=operation_id,
            )
        return quote(str(value), safe="")

    url = base_url + re.sub(r"\{([^}]+)\}", fill, template)
    pairs = [
        (key, ("true" if value else "false") if isinstance(value, bool) else str(value))
        for key, value in (query or {}).items()
        if value is not None
    ]
    return f"{url}?{urlencode(pairs)}" if pairs else url


def _meta(operation_id: str, response: httpx.Response, attempt: int) -> ResponseMeta:
    retry_after = parse_retry_after(response.headers.get("retry-after"))
    replayed = response.headers.get("idempotent-replayed")
    return ResponseMeta(
        operation_id=operation_id,
        status=response.status_code,
        attempt=attempt,
        request_id=response.headers.get("x-request-id"),
        idempotent_replayed=None if replayed is None else replayed == "true",
        rate_limit=response.headers.get("ratelimit"),
        rate_limit_policy=response.headers.get("ratelimit-policy"),
        retry_after_seconds=None if retry_after is None else math.ceil(retry_after),
        headers=response.headers,
    )


def _error_body(response: httpx.Response) -> Any:
    text = response.read().decode("utf-8", errors="replace")
    if not text:
        return None
    try:
        return _json.loads(text)
    except ValueError:
        return text


class Requester:
    def __init__(self, config: RequesterConfig) -> None:
        self._config = config
        self._auth = None if config.api_key is None else _BearerAuth(config.api_key)
        self._secrets: tuple[str, ...] = () if config.api_key is None else (config.api_key,)
        parts = urlsplit(config.base_url)
        self._origin = f"{parts.scheme}://{parts.netloc}"

    def call(
        self,
        operation_id: str,
        *,
        path: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        json: Any = _UNSET,
        form: tuple[str, bytes, str] | None = None,
        idempotency_key: str | None = None,
        wait: float | None = None,
        accept: str = "application/json",
        min_timeout: float = 0.0,
        read_only: bool = False,
        raw: Callable[[httpx.Response], Any] | None = None,
        keep_open: bool = False,
        anonymous: bool = False,
        oauth_errors: bool = False,
        options: RequestOptions | None = None,
    ) -> Any:
        operation = OPERATIONS[operation_id]
        opts: RequestOptions = options or {}
        if not anonymous and self._auth is None:
            raise StoreshotError(
                "MISSING_API_KEY",
                f"{operation_id} needs an API key; this client was created with api_key=None "
                "(get one with client.auth.link_account()).",
                operation_id=operation_id,
            )
        url = build_url(self._config.base_url, operation_id, path, query)
        headers = {
            **self._config.default_headers,
            **user_headers(opts.get("headers")),
            "User-Agent": self._config.user_agent,
            "X-Storeshot-Client": self._config.client_header,
            "Accept": accept,
        }
        content: bytes | None = None
        if json is not _UNSET:
            headers["Content-Type"] = "application/json"
            content = _json.dumps(json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if wait is not None:
            headers["Prefer"] = f"wait={max(0, math.floor(wait))}"
        if "request_id" in opts:
            assert_request_id(opts["request_id"])
            headers["X-Request-Id"] = opts["request_id"]
        keyed = False
        if operation.idempotency_key and not read_only:
            key = idempotency_key if idempotency_key is not None else str(uuid.uuid4())
            if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
                raise StoreshotError(
                    "INVALID_CONFIGURATION",
                    "idempotency_key must be 1–255 printable ASCII characters.",
                    operation_id=operation_id,
                )
            assert_header_value("Idempotency-Key", key)
            headers["Idempotency-Key"] = key
            keyed = True
        retry_safe = (
            operation.method == "GET" or keyed or read_only or operation_id in READ_ONLY_POSTS
        )
        timeout = max(opts.get("timeout", self._config.timeout), min_timeout)
        max_retries = opts.get("max_retries", self._config.max_retries)
        hint = "" if retry_safe else MAYBE_PROCESSED
        hooks = [h for h in (self._config.on_response, opts.get("on_response")) if h is not None]
        http = self._config.http
        attempt = 0
        while True:
            request = http.build_request(
                operation.method,
                url,
                headers=headers,
                content=content,
                files=None if form is None else {"file": form},
                timeout=httpx.Timeout(timeout),
            )
            response: httpx.Response | None = None
            hold = False
            failure: StoreshotError
            outcome: AttemptOutcome
            try:
                response = http.send(
                    request,
                    # None disables auth entirely (anonymous operations, key-less clients).
                    auth=None if anonymous else self._auth,
                    stream=True,
                    follow_redirects=False,
                )
                meta = _meta(operation_id, response, attempt)
                for hook in hooks:
                    hook(meta)
                if response.is_success:
                    if raw is not None:
                        value = raw(response)
                        hold = keep_open
                        return value
                    body = response.read()
                    if response.status_code == 204 or not body:
                        return None
                    try:
                        return _json.loads(body)
                    except ValueError:
                        raise StoreshotError(
                            "UNEXPECTED_RESPONSE",
                            f"HTTP {response.status_code} with a body that is not JSON.",
                            status=response.status_code,
                            request_id=meta.request_id,
                            operation_id=operation_id,
                        ) from None
                error_body = _error_body(response)
                if (
                    oauth_errors
                    and response.status_code == 400
                    and isinstance(error_body, dict)
                    and isinstance(error_body.get("error"), str)
                ):
                    description = error_body.get("error_description")
                    return OAuthError(
                        error=error_body["error"],
                        error_description=description if isinstance(description, str) else None,
                    )
                failure = error_from_response(
                    status=response.status_code,
                    body=error_body,
                    headers=response.headers,
                    operation_id=operation_id,
                    secrets=self._secrets,
                )
                outcome = AttemptOutcome(
                    "status",
                    status=response.status_code,
                    code=None if failure.code == "UNEXPECTED_RESPONSE" else failure.code,
                    retry_after=parse_retry_after(response.headers.get("retry-after")),
                )
            except StoreshotError:
                raise
            except httpx.TimeoutException as error:
                outcome = AttemptOutcome("timeout")
                failure = StoreshotTimeoutError(
                    "TIMEOUT",
                    f"No answer from {self._origin} within {timeout:g} s.{hint}",
                    operation_id=operation_id,
                    secrets=self._secrets,
                )
                failure.__cause__ = error
            except httpx.RequestError as error:
                outcome = AttemptOutcome("network")
                failure = StoreshotConnectionError(
                    "CONNECTION_ERROR",
                    f"Could not reach {self._origin}: {error}.{hint}",
                    operation_id=operation_id,
                    secrets=self._secrets,
                )
                failure.__cause__ = error
            finally:
                if response is not None and not hold:
                    response.close()
            decision = decide_retry(
                retry_safe=retry_safe,
                outcome=outcome,
                attempt=attempt,
                max_retries=max_retries,
                max_retry_after=self._config.max_retry_after,
            )
            if not decision.retry:
                raise failure
            clock.sleep(decision.delay)
            attempt += 1
