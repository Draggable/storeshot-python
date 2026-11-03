"""Typing names that moved into `typing` in Python 3.11 (SS-026 §3.2)."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from typing import NotRequired, Required, TypedDict, Unpack, get_type_hints, is_typeddict
else:  # pragma: no cover - exercised by the Python 3.10 CI leg
    from typing_extensions import (
        NotRequired,
        Required,
        TypedDict,
        Unpack,
        get_type_hints,
        is_typeddict,
    )

__all__ = ["NotRequired", "Required", "TypedDict", "Unpack", "get_type_hints", "is_typeddict"]
