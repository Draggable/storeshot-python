"""list_all (SS-026 §6.6)."""

from __future__ import annotations

import itertools
from typing import Any

import httpx
import pytest
from _mock import MockApi

from storeshot._errors import StoreshotError


def page(ids: list[str], cursor: str | None) -> Any:
    body = {"data": [{"id": i} for i in ids], "nextCursor": cursor}
    return lambda _r: httpx.Response(200, json=body)


def test_list_all_follows_cursors_lazily(api: MockApi) -> None:
    api.on("GET", "/generations", page(["a", "b"], "c1"), page(["c"], None))
    items = api.client().generations.list_all({"limit": 2, "status": "succeeded"})
    assert api.requests == []
    assert [g["id"] for g in items] == ["a", "b", "c"]
    assert "cursor" not in api.requests[0].url.params
    assert api.requests[1].url.params["cursor"] == "c1"
    assert api.requests[1].url.params["status"] == "succeeded"


def test_islice_stops_early(api: MockApi) -> None:
    api.on("GET", "/uploads", page(["a", "b"], "c1"))
    assert [u["id"] for u in itertools.islice(api.client().uploads.list_all(), 1)] == ["a"]
    assert len(api.requests) == 1


def test_repeated_cursor_stops(api: MockApi) -> None:
    api.on("GET", "/projects", page(["a"], "same"))
    with pytest.raises(StoreshotError) as info:
        list(api.client().projects.list_all())
    assert info.value.code == "UNEXPECTED_RESPONSE"


def test_webhook_deliveries_and_activity(api: MockApi) -> None:
    api.on("GET", "/webhooks/w1/deliveries", page(["d1"], None))
    api.on("GET", "/activity", page(["e1"], None))
    api.on("GET", "/screenshot-sets", page(["s1"], None))
    c = api.client()
    assert [d["id"] for d in c.webhooks.list_all_deliveries("w1")] == ["d1"]
    assert [e["id"] for e in c.activity.list_all()] == ["e1"]
    assert [s["id"] for s in c.screenshot_sets.list_all()] == ["s1"]
