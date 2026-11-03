"""Webhook signature verification (SS-026 §7.4) against the signer-pinned vectors."""

from __future__ import annotations

import base64
import json
from typing import Any

import inputs
import pytest

from storeshot._errors import StoreshotWebhookError
from storeshot.webhooks import construct_webhook_event, verify_webhook_signature

VECTORS: list[dict[str, Any]] = json.loads(inputs.input_path("webhook_vectors").read_text("utf-8"))[
    "vectors"
]


def load_snippet() -> dict[str, Any]:
    """Executes the docs' verifier from its source (never imported: no __pycache__ next to it)."""
    path = inputs.input_path("webhook_snippet")
    namespace: dict[str, Any] = {"__name__": "verify_webhook"}
    exec(compile(path.read_text("utf-8"), str(path), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_signer_pinned_vectors(vector: dict[str, Any]) -> None:
    body, now, header = (
        base64.b64decode(vector["bodyBase64"]),
        vector["timestamp"],
        vector["header"],
    )
    secrets = vector["secrets"]
    assert verify_webhook_signature(body, header, secrets, now=now) is True
    assert verify_webhook_signature(memoryview(body), header, secrets, now=now) is True
    assert verify_webhook_signature(bytearray(body), header, secrets, now=now) is True
    assert verify_webhook_signature(body.decode("utf-8"), header, secrets, now=now) is True
    assert verify_webhook_signature(body, header, "whsec_wrong", now=now) is False


def test_agrees_with_the_docs_snippet() -> None:
    snippet = load_snippet()
    for vector in VECTORS:
        body, now = base64.b64decode(vector["bodyBase64"]), vector["timestamp"]
        for secret in [*vector["secrets"], "whsec_wrong"]:
            ours = verify_webhook_signature(body, vector["header"], secret, now=now)
            theirs = snippet["verify_storeshot_signature"](body, vector["header"], secret, now=now)
            assert ours == theirs, vector["name"]


def test_tolerance_and_malformed_headers() -> None:
    v = VECTORS[0]
    body, header, secrets, t = (
        base64.b64decode(v["bodyBase64"]),
        v["header"],
        v["secrets"],
        v["timestamp"],
    )
    assert verify_webhook_signature(body, header, secrets, now=t + 300) is True
    assert verify_webhook_signature(body, header, secrets, now=t + 301) is False
    assert verify_webhook_signature(body, header, secrets, now=t - 301) is False
    assert verify_webhook_signature(body, header, secrets, now=t + 301, tolerance_seconds=400)
    v1 = header.split(",")[1]
    bad_headers = [
        None,
        "",
        f"t={t}",
        f"t={t},t={t},{v1}",
        header.replace("v1=", "v1=zz"),
        header.replace(f"t={t}", "t=١٧٩٢٦٦٣٢٠٠"),  # Arabic-Indic digits: never ASCII-valid
        header.replace(f"t={t}", f"t=+{t}"),
    ]
    for bad in bad_headers:
        assert verify_webhook_signature(body, bad, secrets, now=t) is False, bad
    assert verify_webhook_signature(body, header, ["", "wrong"], now=t) is False
    assert verify_webhook_signature(body + b" ", header, secrets, now=t) is False


def test_construct_webhook_event() -> None:
    v = VECTORS[0]
    body = base64.b64decode(v["bodyBase64"])
    event = construct_webhook_event(body, v["header"], v["secrets"], now=v["timestamp"])
    assert isinstance(event["type"], str)
    with pytest.raises(StoreshotWebhookError) as info:
        construct_webhook_event(body + b" ", v["header"], v["secrets"], now=v["timestamp"])
    assert info.value.code == "WEBHOOK_SIGNATURE_INVALID"


def test_signed_non_event_is_payload_invalid() -> None:
    empty = next(v for v in VECTORS if v["name"] == "empty-object")
    body = base64.b64decode(empty["bodyBase64"])
    with pytest.raises(StoreshotWebhookError) as info:
        construct_webhook_event(body, empty["header"], empty["secrets"], now=empty["timestamp"])
    assert info.value.code == "WEBHOOK_PAYLOAD_INVALID"
