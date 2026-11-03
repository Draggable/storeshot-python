"""Plain resources send the right method, path, query and body (SS-026 §4.2)."""

from __future__ import annotations

import json

import httpx
from _mock import MockApi


def test_plain_resources_send_the_right_requests(api: MockApi) -> None:
    api.fallback = lambda _r: httpx.Response(200, json={})
    c = api.client()
    c.devices.list({"store": "app_store"})
    c.stores.requirements("google_play")
    c.api_keys.create({"name": "k", "environment": "test"})
    c.api_keys.revoke("k1")
    c.usage.get({"from": "2026-10-01", "groupBy": "source"})
    c.projects.update("p1", {"name": "n"})
    c.projects.remove_items("p1", {"generationIds": ["g1"]})
    c.webhooks.rotate_secret("w1")
    c.webhooks.list_deliveries("w1", {"limit": 2})
    c.billing.create_checkout({"pack": "credits_15"}, idempotency_key="order-1")
    c.billing.create_portal_session()
    c.generations.get("g1", wait=90)
    got = [(r.method, r.url.raw_path.decode()) for r in api.requests]
    assert got == [
        ("GET", "/v1/devices?store=app_store"),
        ("GET", "/v1/stores/google_play/requirements"),
        ("POST", "/v1/api-keys"),
        ("DELETE", "/v1/api-keys/k1"),
        ("GET", "/v1/usage?from=2026-10-01&groupBy=source"),
        ("PATCH", "/v1/projects/p1"),
        ("POST", "/v1/projects/p1/items/remove"),
        ("POST", "/v1/webhooks/w1/rotate-secret"),
        ("GET", "/v1/webhooks/w1/deliveries?limit=2"),
        ("POST", "/v1/billing/checkout"),
        ("POST", "/v1/billing/portal"),
        ("GET", "/v1/generations/g1"),
    ]
    assert json.loads(api.requests[6].content) == {"generationIds": ["g1"]}
    assert json.loads(api.requests[7].content) == {}
    assert api.requests[9].headers["idempotency-key"] == "order-1"
    assert api.requests[11].headers["prefer"] == "wait=60"  # capped at the server's 60 s
