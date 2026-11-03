from __future__ import annotations

import httpx

from storeshot._errors import (
    SDK_ERROR_CODES,
    StoreshotConnectionError,
    StoreshotError,
    StoreshotTimeoutError,
    StoreshotWebhookError,
    error_from_response,
)

KEY = "ss_test_" + "Ab3dEf6hIj9kLm2nOp5qRs8t"


def test_envelope() -> None:
    body = {
        "error": {
            "code": "INSUFFICIENT_CREDITS",
            "message": "Top up.",
            "requestId": "req_1",
            "docUrl": "https://storeshot.art/docs/errors/#insufficient_credits",
            "details": {"topUpUrl": "https://x", "requiredCredits": 4},
        }
    }
    error = error_from_response(
        status=402,
        body=body,
        headers=httpx.Headers({"retry-after": "3"}),
        operation_id="createScreenshotSet",
    )
    assert (error.status, error.code, error.request_id) == (402, "INSUFFICIENT_CREDITS", "req_1")
    assert error.retry_after_seconds == 3 and error.operation_id == "createScreenshotSet"
    assert error.details == {"topUpUrl": "https://x", "requiredCredits": 4}
    assert error.doc_url == "https://storeshot.art/docs/errors/#insufficient_credits"
    assert str(error) == "StoreshotError [402 INSUFFICIENT_CREDITS]: Top up. (request req_1)"
    assert error.to_dict()["requestId"] == "req_1"


def test_non_envelope_uses_the_header_request_id() -> None:
    headers = httpx.Headers({"x-request-id": "r2"})
    error = error_from_response(status=502, body="<html>", headers=headers, operation_id=None)
    assert (error.code, error.request_id, error.status) == ("UNEXPECTED_RESPONSE", "r2", 502)


def test_messages_and_details_are_scrubbed() -> None:
    body = {"error": {"code": "INVALID_INPUT", "message": f"bad {KEY}", "details": {"k": [KEY]}}}
    error = error_from_response(
        status=422, body=body, headers=httpx.Headers(), operation_id=None, secrets=[KEY]
    )
    assert KEY not in str(error) and KEY not in repr(error) and KEY not in str(error.to_dict())


def test_subclasses_and_codes() -> None:
    for cls in (StoreshotConnectionError, StoreshotTimeoutError, StoreshotWebhookError):
        assert issubclass(cls, StoreshotError)
    assert "NODE_ONLY" not in SDK_ERROR_CODES and len(SDK_ERROR_CODES) == 13
