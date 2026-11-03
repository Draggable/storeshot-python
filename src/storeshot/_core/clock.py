"""Time and randomness seams (SS-026 §6.2): tests replace these module attributes.

Callers import the module (`from . import clock`) and call `clock.sleep(...)`, so that
monkeypatching works.
"""

from __future__ import annotations

import random as _random
import time as _time


def sleep(seconds: float) -> None:
    _time.sleep(seconds)


def monotonic() -> float:
    return _time.monotonic()


def time() -> float:
    return _time.time()


def random() -> float:
    return _random.random()
