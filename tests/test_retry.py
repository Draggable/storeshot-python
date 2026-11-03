"""The TS SDK's retry.test.ts decision table, in seconds (SS-026 §6.2)."""

from __future__ import annotations

import pytest

from storeshot._core.retry import (
    BACKOFF_BASE,
    BACKOFF_CAP,
    AttemptOutcome,
    backoff,
    decide_retry,
    parse_retry_after,
)


def decide(
    outcome: AttemptOutcome,
    *,
    safe: bool = True,
    attempt: int = 0,
    max_retries: int = 2,
    max_after: float = 60.0,
) -> tuple[bool, float, str]:
    d = decide_retry(
        retry_safe=safe,
        outcome=outcome,
        attempt=attempt,
        max_retries=max_retries,
        max_retry_after=max_after,
        random=lambda: 0.5,
    )
    return d.retry, d.delay, d.reason


def status(code: int, error: str | None = None, after: float | None = None) -> AttemptOutcome:
    return AttemptOutcome("status", status=code, code=error, retry_after=after)


def test_client_errors_are_never_retried() -> None:
    for code in (400, 401, 402, 404, 409, 422):
        assert decide(status(code)) == (False, 0.0, "not_retryable")


def test_429_is_retried_for_unsafe_requests_too() -> None:
    assert decide(status(429, "RATE_LIMITED", 2.0), safe=False) == (True, 2.1, "")
    assert decide(status(429), safe=False) == (True, BACKOFF_BASE * 0.75, "")


def test_503_refusal_needs_retry_after_and_a_refusal_code() -> None:
    assert decide(status(503, "SERVICE_UNAVAILABLE", 1.0), safe=False)[0] is True
    assert decide(status(503, "BILLING_UNAVAILABLE", 1.0), safe=False)[0] is True
    assert decide(status(503, "SERVICE_UNAVAILABLE"), safe=False) == (False, 0.0, "unsafe")
    assert decide(status(503, "INTERNAL_ERROR", 1.0), safe=False) == (False, 0.0, "unsafe")


def test_5xx_network_and_timeouts_only_when_safe() -> None:
    for outcome in (status(500), status(502), AttemptOutcome("network"), AttemptOutcome("timeout")):
        assert decide(outcome, safe=False) == (False, 0.0, "unsafe")
        assert decide(outcome, safe=True) == (True, BACKOFF_BASE * 0.75, "")


def test_exhausted_and_long_retry_after() -> None:
    assert decide(status(500), attempt=2) == (False, 0.0, "exhausted")
    assert decide(status(429, after=3600.0)) == (False, 0.0, "retry_after_too_long")


def test_backoff_is_capped_with_equal_jitter() -> None:
    assert backoff(0, lambda: 0.0) == BACKOFF_BASE / 2
    assert backoff(1, lambda: 1.0) == BACKOFF_BASE * 2
    assert backoff(10, lambda: 1.0) == BACKOFF_CAP


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5", 5.0),
        (" 0 ", 0.0),
        ("Thu, 01 Jan 1970 00:00:10 GMT", 10.0),
        ("Thu, 01 Jan 1970 00:00:00 GMT", 0.0),
        ("1.5", None),
        ("-3", None),
        ("soon-ish", None),
        (None, None),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value, now=0.0) == expected
