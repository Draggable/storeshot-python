"""Wait for a generation or a set to finish (SS-026 §6.7; the TS SDK's helpers/wait.ts)."""

from __future__ import annotations

import math
from collections.abc import Callable

from .._core import clock
from .._errors import StoreshotTimeoutError
from .._generated.schemas import Generation, ScreenshotSet

GENERATION_FINAL = ("succeeded", "failed", "canceled")
SCREENSHOT_SET_FINAL = ("succeeded", "partially_failed", "failed", "canceled")
DEFAULT_WAIT_TIMEOUT = 600.0
DEFAULT_POLL_INTERVAL = 3.0


def _timed_out(kind: str, id: str, status: str | None, timeout: float) -> StoreshotTimeoutError:
    return StoreshotTimeoutError(
        "WAIT_TIMEOUT",
        f"{kind} {id} is still {status or 'unfinished'} after {timeout:g} s.",
        details={"id": id, "status": status},
    )


def wait_for_generation(
    get: Callable[[str, int], Generation],
    target: str | Generation,
    *,
    timeout: float,
    poll_interval: float,
) -> Generation:
    """Long-polls with Prefer: wait until final; a failed or canceled generation is returned."""
    if not isinstance(target, str) and target["status"] in GENERATION_FINAL:
        return target
    id = target if isinstance(target, str) else target["id"]
    status: str | None = None if isinstance(target, str) else target["status"]
    deadline = clock.monotonic() + timeout
    while True:
        remaining = deadline - clock.monotonic()
        if remaining <= 0:
            raise _timed_out("Generation", id, status, timeout)
        wait = min(60, math.floor(remaining))
        started = clock.monotonic()
        generation = get(id, wait)
        status = generation["status"]
        if status in GENERATION_FINAL:
            return generation
        # A busy server answers at once; wait=0 (the last second) would otherwise loop tight (F12).
        if wait == 0 or clock.monotonic() - started < wait / 2:
            pause = min(poll_interval, deadline - clock.monotonic())
            if pause > 0:
                clock.sleep(pause)


def wait_for_screenshot_set(
    get: Callable[[str], ScreenshotSet],
    target: str | ScreenshotSet,
    *,
    timeout: float,
    poll_interval: float,
) -> ScreenshotSet:
    """Polls every poll_interval seconds until the set is final, and returns it."""
    if not isinstance(target, str) and target["status"] in SCREENSHOT_SET_FINAL:
        return target
    id = target if isinstance(target, str) else target["id"]
    status: str | None = None if isinstance(target, str) else target["status"]
    deadline = clock.monotonic() + timeout
    first = isinstance(target, str)
    while True:
        if not first:
            pause = min(poll_interval, deadline - clock.monotonic())
            if pause <= 0:
                raise _timed_out("Screenshot set", id, status, timeout)
            clock.sleep(pause)
        first = False
        current = get(id)
        status = current["status"]
        if status in SCREENSHOT_SET_FINAL:
            return current
        if clock.monotonic() >= deadline:
            raise _timed_out("Screenshot set", id, status, timeout)
