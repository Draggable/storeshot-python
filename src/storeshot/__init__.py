"""The official Python SDK for the Storeshot API (SS-026). See README.md."""

from __future__ import annotations

from ._client import DEFAULT_BASE_URL, Storeshot
from ._errors import (
    SDK_ERROR_CODES,
    StoreshotConnectionError,
    StoreshotError,
    StoreshotTimeoutError,
    StoreshotWebhookError,
)
from ._generated.operations import CONTRACT_VERSION, ERROR_CODES, WEBHOOK_EVENT_TYPES
from ._version import __version__
from .webhooks import (
    DEFAULT_WEBHOOK_TOLERANCE_SECONDS,
    WEBHOOK_SIGNATURE_HEADER,
    construct_webhook_event,
    verify_webhook_signature,
)

SDK_VERSION = __version__

__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_BASE_URL",
    "DEFAULT_WEBHOOK_TOLERANCE_SECONDS",
    "ERROR_CODES",
    "SDK_ERROR_CODES",
    "SDK_VERSION",
    "WEBHOOK_EVENT_TYPES",
    "WEBHOOK_SIGNATURE_HEADER",
    "Storeshot",
    "StoreshotConnectionError",
    "StoreshotError",
    "StoreshotTimeoutError",
    "StoreshotWebhookError",
    "__version__",
    "construct_webhook_event",
    "verify_webhook_signature",
]
