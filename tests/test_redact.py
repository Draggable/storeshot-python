from __future__ import annotations

from storeshot._core.redact import mask_key, scrub, scrub_value

KEY = "ss_test_" + "Ab3dEf6hIj9kLm2nOp5qRs8t"


def test_scrub_removes_the_key_and_key_shapes() -> None:
    text = f"bad {KEY} and ss_live_ABCDEFGH12"
    assert scrub(text, [KEY]) == "bad [redacted] and ss_live_[redacted]"


def test_scrub_value_walks_nested_details() -> None:
    details = {"a": [f"x {KEY}"], "b": {"c": KEY}, "n": 3}
    assert scrub_value(details, [KEY]) == {"a": ["x [redacted]"], "b": {"c": "[redacted]"}, "n": 3}


def test_mask_key() -> None:
    assert mask_key(KEY) == "ss_test_…"
    assert mask_key("eyJhbGciOi") == "…"
