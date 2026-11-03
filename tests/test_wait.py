"""Waits (SS-026 §6.7)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from _mock import MockApi

from storeshot._errors import StoreshotTimeoutError


def gen(status: str) -> Any:
    return lambda _r: httpx.Response(200, json={"id": "g1", "status": status})


def test_wait_for_generation_long_polls_with_prefer_wait(api: MockApi) -> None:
    api.on("GET", "/generations/g1", gen("running"), gen("succeeded"))
    done = api.client().wait_for_generation("g1")
    assert done["status"] == "succeeded"
    assert api.requests[0].headers["prefer"] == "wait=60"


def test_final_target_is_returned_without_a_request(api: MockApi) -> None:
    final: Any = {"id": "g1", "status": "failed"}
    assert api.client().wait_for_generation(final) is final
    assert api.requests == []


def test_failed_is_returned_not_raised(api: MockApi) -> None:
    api.on("GET", "/generations/g1", gen("canceled"))
    assert api.client().wait_for_generation("g1")["status"] == "canceled"


def test_wait_timeout(api: MockApi) -> None:
    api.on("GET", "/generations/g1", gen("queued"))
    with pytest.raises(StoreshotTimeoutError) as info:
        api.client().wait_for_generation("g1", timeout=5)
    assert info.value.code == "WAIT_TIMEOUT"
    assert info.value.details == {"id": "g1", "status": "queued"}


def test_no_tight_loop_in_the_last_second(api: MockApi) -> None:
    api.on("GET", "/generations/g1", gen("queued"))
    with pytest.raises(StoreshotTimeoutError):
        api.client().wait_for_generation("g1", timeout=0.5, poll_interval=3)
    assert len(api.requests) == 1  # F12: the TS SDK fires requests back to back here


def test_wait_for_screenshot_set_polls_every_interval(api: MockApi, fake_clock: Any) -> None:
    api.on(
        "GET",
        "/screenshot-sets/s1",
        lambda _r: httpx.Response(200, json={"id": "s1", "status": "running"}),
        lambda _r: httpx.Response(200, json={"id": "s1", "status": "partially_failed"}),
    )
    queued: Any = {"id": "s1", "status": "queued"}
    done = api.client().wait_for_screenshot_set(queued)
    assert done["status"] == "partially_failed"
    assert fake_clock.sleeps == [3.0, 3.0]


def test_wait_for_screenshot_set_by_id_polls_at_once_and_times_out(
    api: MockApi, fake_clock: Any
) -> None:
    api.on(
        "GET",
        "/screenshot-sets/s1",
        lambda _r: httpx.Response(200, json={"id": "s1", "status": "running"}),
    )
    with pytest.raises(StoreshotTimeoutError):
        api.client().wait_for_screenshot_set("s1", timeout=7)
    assert fake_clock.sleeps == [3.0, 3.0, 1.0] and len(api.requests) == 4
