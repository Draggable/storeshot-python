"""Errors (SS-026 §4.3): one class with the API's code, three subclasses; messages are scrubbed."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import httpx

from ._core.redact import scrub, scrub_value
from ._core.retry import parse_retry_after

#: Codes the SDK raises itself (the TS list without NODE_ONLY); never one of the API's ErrorCodes.
SDK_ERROR_CODES = (
    "MISSING_API_KEY",
    "INVALID_CONFIGURATION",
    "BROWSER_NOT_ALLOWED",
    "CONNECTION_ERROR",
    "TIMEOUT",
    "WAIT_TIMEOUT",
    "UNEXPECTED_RESPONSE",
    "FILE_TOO_LARGE",
    "WEBHOOK_SIGNATURE_INVALID",
    "WEBHOOK_PAYLOAD_INVALID",
    "DEVICE_ACCESS_DENIED",
    "DEVICE_CODE_EXPIRED",
    "DEVICE_INVALID_GRANT",
)
SdkErrorCode = Literal[
    "MISSING_API_KEY",
    "INVALID_CONFIGURATION",
    "BROWSER_NOT_ALLOWED",
    "CONNECTION_ERROR",
    "TIMEOUT",
    "WAIT_TIMEOUT",
    "UNEXPECTED_RESPONSE",
    "FILE_TOO_LARGE",
    "WEBHOOK_SIGNATURE_INVALID",
    "WEBHOOK_PAYLOAD_INVALID",
    "DEVICE_ACCESS_DENIED",
    "DEVICE_CODE_EXPIRED",
    "DEVICE_INVALID_GRANT",
]


class StoreshotError(Exception):
    """Every error the SDK raises for an API answer or a failed request."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 0,
        request_id: str | None = None,
        doc_url: str | None = None,
        details: Mapping[str, Any] | None = None,
        retry_after_seconds: int | None = None,
        operation_id: str | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        self.message = scrub(message, secrets)
        super().__init__(self.message)
        #: An API ErrorCode, an SDK code, or a code added to the API after this SDK was built.
        self.code = code
        #: HTTP status; 0 when there was no response.
        self.status = status
        self.request_id = request_id
        self.doc_url = doc_url
        self.details: dict[str, Any] | None = (
            None if details is None else scrub_value(dict(details), secrets)
        )
        self.retry_after_seconds = retry_after_seconds
        self.operation_id = operation_id

    def __str__(self) -> str:
        where = f" (request {self.request_id})" if self.request_id else ""
        return f"{type(self).__name__} [{self.status} {self.code}]: {self.message}{where}"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, status={self.status}, "
            f"request_id={self.request_id!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "requestId": self.request_id,
            "docUrl": self.doc_url,
            "details": self.details,
            "retryAfterSeconds": self.retry_after_seconds,
            "operationId": self.operation_id,
        }


class StoreshotConnectionError(StoreshotError):
    """No answer: DNS, connection, TLS or a reset before the response arrived."""


class StoreshotTimeoutError(StoreshotError):
    """An attempt ran out of time (TIMEOUT) or a wait helper did (WAIT_TIMEOUT)."""


class StoreshotWebhookError(StoreshotError):
    """A webhook payload whose signature or body is not acceptable."""


def error_from_response(
    *,
    status: int,
    body: Any,
    headers: httpx.Headers,
    operation_id: str | None,
    secrets: Sequence[str] = (),
) -> StoreshotError:
    """The StoreshotError for a non-2xx answer (parsed JSON body, the raw text, or None)."""
    retry_after = parse_retry_after(headers.get("retry-after"))
    header_request_id = headers.get("x-request-id")
    retry_after_seconds = None if retry_after is None else math.ceil(retry_after)
    error = body.get("error") if isinstance(body, dict) else None
    if (
        isinstance(error, dict)
        and isinstance(error.get("code"), str)
        and isinstance(error.get("message"), str)
    ):
        details = error.get("details")
        request_id = error.get("requestId")
        doc_url = error.get("docUrl")
        return StoreshotError(
            error["code"],
            error["message"],
            status=status,
            request_id=request_id if isinstance(request_id, str) else header_request_id,
            doc_url=doc_url if isinstance(doc_url, str) else None,
            details=details if isinstance(details, dict) else None,
            retry_after_seconds=retry_after_seconds,
            operation_id=operation_id,
            secrets=secrets,
        )
    return StoreshotError(
        "UNEXPECTED_RESPONSE",
        f"HTTP {status} without a Storeshot error body.",
        status=status,
        request_id=header_request_id,
        retry_after_seconds=retry_after_seconds,
        operation_id=operation_id,
        secrets=secrets,
    )
