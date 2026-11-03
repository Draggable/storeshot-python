"""A runtime check of JSON values against the generated TypedDict hints (SS-026 §10.1, §10.4)."""

from __future__ import annotations

import types
from typing import Any, Literal, Union, get_args, get_origin

from storeshot._compat import get_type_hints, is_typeddict


def check(value: Any, hint: Any, path: str = "$") -> list[str]:
    """Problems of `value` against `hint` (empty = matches). Unknown keys are problems."""
    if hint is Any:
        return []
    if is_typeddict(hint):
        if not isinstance(value, dict):
            return [f"{path}: expected an object, got {type(value).__name__}"]
        hints = get_type_hints(hint)
        problems = [
            f"{path}: missing {k}" for k in sorted(hint.__required_keys__) if k not in value
        ]
        for key, item in value.items():
            if key not in hints:
                problems.append(f"{path}.{key}: not in {hint.__name__}")
            else:
                problems += check(item, hints[key], f"{path}.{key}")
        return problems
    origin, args = get_origin(hint), get_args(hint)
    if origin in (Union, types.UnionType):
        results = [check(value, alt, path) for alt in args]
        if any(not r for r in results):
            return []
        return [f"{path}: matches no alternative ({min(results, key=len)[0]})"]
    if origin is Literal:
        ok = any(type(value) is type(a) and value == a for a in args)
        return [] if ok else [f"{path}: {value!r} not in {args}"]
    if origin is list:
        if not isinstance(value, list):
            return [f"{path}: expected a list"]
        return [p for i, item in enumerate(value) for p in check(item, args[0], f"{path}[{i}]")]
    if origin is dict:
        if not isinstance(value, dict):
            return [f"{path}: expected an object"]
        return [p for k, item in value.items() for p in check(item, args[1], f"{path}.{k}")]
    if hint is type(None):
        return [] if value is None else [f"{path}: expected null"]
    if hint is bool:
        return [] if isinstance(value, bool) else [f"{path}: expected a boolean"]
    if hint is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
        return [] if ok else [f"{path}: expected an integer"]
    if hint is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return [] if ok else [f"{path}: expected a number"]
    if hint is str:
        return [] if isinstance(value, str) else [f"{path}: expected a string"]
    if hint is bytes:
        return [] if isinstance(value, bytes) else [f"{path}: expected bytes"]
    return [f"{path}: unsupported hint {hint!r}"]
