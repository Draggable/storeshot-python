"""Webhook signature verification (SS-026 §7.4), exactly as https://storeshot.art/docs/webhooks/
describes: one `t` of ASCII digits within the tolerance, HMAC-SHA256(secret, `<t>.<raw body>`),
any 64-hex `v1` matching (two during a secret rotation), compared with hmac.compare_digest."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Sequence
from typing import TypeAlias, cast

from ._core import clock
from ._errors import StoreshotWebhookError
from ._generated.schemas import WebhookEvent

#: The header that carries `t=<unix seconds>,v1=<hex>[,v1=<hex>]`.
WEBHOOK_SIGNATURE_HEADER = "Storeshot-Signature"
DEFAULT_WEBHOOK_TOLERANCE_SECONDS = 300
# ASCII only: Python's \d and str.isdigit() also accept other scripts' digits.
_TIMESTAMP = re.compile(r"[0-9]+", re.ASCII)
_HEX64 = re.compile(r"[0-9a-fA-F]{64}", re.ASCII)
Payload: TypeAlias = bytes | bytearray | memoryview | str


def _to_bytes(payload: Payload) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)


def verify_webhook_signature(
    payload: Payload,
    signature: str | None,
    secret: str | Sequence[str],
    *,
    tolerance_seconds: float = DEFAULT_WEBHOOK_TOLERANCE_SECONDS,
    now: float | None = None,
) -> bool:
    """True when `signature` (the Storeshot-Signature header) signs the raw `payload` with the
    secret (or one of several, while you rotate your own configuration)."""
    if not isinstance(signature, str) or signature == "":
        return False
    items = [part.strip().split("=") for part in signature.split(",")]
    timestamps = [item[1] if len(item) > 1 else "" for item in items if item[0] == "t"]
    if len(timestamps) != 1 or not _TIMESTAMP.fullmatch(timestamps[0]):
        return False
    current = clock.time() if now is None else now
    if abs(current - int(timestamps[0])) > tolerance_seconds:
        return False
    candidates = [
        bytes.fromhex(item[1])
        for item in items
        if item[0] == "v1" and len(item) > 1 and _HEX64.fullmatch(item[1])
    ]
    if not candidates:
        return False
    signed = timestamps[0].encode("ascii") + b"." + _to_bytes(payload)
    secrets = [secret] if isinstance(secret, str) else list(secret)
    for value in secrets:
        if not value:
            continue
        expected = hmac.new(value.encode("utf-8"), signed, hashlib.sha256).digest()
        for candidate in candidates:
            if hmac.compare_digest(expected, candidate):
                return True
    return False


def construct_webhook_event(
    payload: Payload,
    signature: str | None,
    secret: str | Sequence[str],
    *,
    tolerance_seconds: float = DEFAULT_WEBHOOK_TOLERANCE_SECONDS,
    now: float | None = None,
) -> WebhookEvent:
    """Verifies the signature, then parses the event. Raises StoreshotWebhookError
    (WEBHOOK_SIGNATURE_INVALID or WEBHOOK_PAYLOAD_INVALID). Deduplicate on event["id"]."""
    if not verify_webhook_signature(
        payload, signature, secret, tolerance_seconds=tolerance_seconds, now=now
    ):
        raise StoreshotWebhookError(
            "WEBHOOK_SIGNATURE_INVALID",
            "The Storeshot-Signature header does not match this payload and secret (or is too "
            "old). Verify the raw request body.",
        )
    try:
        event = json.loads(_to_bytes(payload))
    except ValueError:
        event = None
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise StoreshotWebhookError(
            "WEBHOOK_PAYLOAD_INVALID", "The webhook payload is not a JSON event with a type."
        )
    return cast(WebhookEvent, event)
