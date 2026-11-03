"""Secrets never leave the SDK in a message (SS-026 §7.1): same rules as the TS SDK."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

#: Storeshot API keys anywhere in a text (the secret part is at least 8 characters).
KEY_PATTERN = re.compile(r"\bss_(live|test)_[A-Za-z0-9_-]{8,}", re.ASCII)
MAX_DEPTH = 8


def scrub(text: str, secrets: Sequence[str] = ()) -> str:
    """Removes the given secrets and anything shaped like an API key from a text."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return KEY_PATTERN.sub(lambda m: f"ss_{m.group(1)}_[redacted]", text)


def scrub_value(value: Any, secrets: Sequence[str] = (), depth: int = 0) -> Any:
    """`scrub` applied to every string of a JSON-like value (error details)."""
    if isinstance(value, str):
        return scrub(value, secrets)
    if depth >= MAX_DEPTH:
        return value
    if isinstance(value, list):
        return [scrub_value(item, secrets, depth + 1) for item in value]
    if isinstance(value, dict):
        return {key: scrub_value(item, secrets, depth + 1) for key, item in value.items()}
    return value


def mask_key(key: str) -> str:
    """What may be shown of a credential: the key environment prefix only."""
    match = re.match(r"ss_(live|test)_", key)
    return f"{match.group(0)}…" if match else "…"
