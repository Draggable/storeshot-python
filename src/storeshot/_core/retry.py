"""When an attempt may be repeated, and after how long (SS-026 §6.2; the TS SDK's retry.ts).

- A 429, or a 503 envelope (SERVICE_UNAVAILABLE/BILLING_UNAVAILABLE) that carries Retry-After, is
  retried for every method: the server refused before doing any work.
- Other 5xx, network errors and timeouts are retried only when repeating is safe: GET, a POST that
  carries an Idempotency-Key, or a read-only POST. Never a plain POST, PATCH or DELETE.
- A Retry-After longer than max_retry_after (e.g. the daily cap until UTC midnight) is not waited
  for.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Literal

from . import clock

BACKOFF_BASE = 0.5
BACKOFF_CAP = 8.0
REFUSAL_CODES = frozenset({"SERVICE_UNAVAILABLE", "BILLING_UNAVAILABLE"})


@dataclass(frozen=True)
class AttemptOutcome:
    kind: Literal["status", "network", "timeout"]
    status: int = 0
    code: str | None = None
    retry_after: float | None = None


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay: float = 0.0
    reason: Literal["", "not_retryable", "unsafe", "exhausted", "retry_after_too_long"] = ""


def backoff(attempt: int, random: Callable[[], float] | None = None) -> float:
    """Capped exponential backoff with equal jitter: [½, 1] × min(cap, base × 2^attempt)."""
    ceiling = min(BACKOFF_CAP, BACKOFF_BASE * 2.0**attempt)
    return round(ceiling * (0.5 + (random or clock.random)() / 2), 3)


def is_refusal(outcome: AttemptOutcome) -> bool:
    """A refusal the server answered before doing any work."""
    if outcome.kind != "status":
        return False
    if outcome.status == 429:
        return True
    return (
        outcome.status == 503 and outcome.retry_after is not None and outcome.code in REFUSAL_CODES
    )


def decide_retry(
    *,
    retry_safe: bool,
    outcome: AttemptOutcome,
    attempt: int,
    max_retries: int,
    max_retry_after: float,
    random: Callable[[], float] | None = None,
) -> RetryDecision:
    rnd = random or clock.random
    transient = outcome.kind != "status" or outcome.status >= 500 or outcome.status == 429
    if not transient:
        return RetryDecision(False, reason="not_retryable")
    if not is_refusal(outcome) and not retry_safe:
        return RetryDecision(False, reason="unsafe")
    if attempt >= max_retries:
        return RetryDecision(False, reason="exhausted")
    if outcome.kind == "status" and outcome.retry_after is not None:
        if outcome.retry_after > max_retry_after:
            return RetryDecision(False, reason="retry_after_too_long")
        return RetryDecision(True, delay=round(outcome.retry_after * (1 + rnd() / 10), 3))
    return RetryDecision(True, delay=backoff(attempt, rnd))


def parse_retry_after(value: str | None, now: float | None = None) -> float | None:
    """Retry-After (delta seconds or an HTTP date) in seconds, or None when absent or invalid."""
    if value is None:
        return None
    text = value.strip()
    if re.fullmatch(r"[0-9]+", text):
        return float(int(text))
    if not re.search(r"[a-z]", text, re.IGNORECASE):
        return None
    try:
        at = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    current = clock.time() if now is None else now
    return max(0.0, at.timestamp() - current)
