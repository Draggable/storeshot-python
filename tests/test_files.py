"""Uploads (SS-026 §6.5)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from _mock import MockApi

from storeshot._errors import StoreshotError
from storeshot._helpers.files import MAX_UPLOAD_BYTES

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def ready(_r: httpx.Request) -> httpx.Response:
    return httpx.Response(201, json={"id": "u1", "status": "ready"})


def test_upload_from_path_bytes_and_file_object(api: MockApi, tmp_path: Path) -> None:
    api.on("POST", "/uploads", ready)
    path = tmp_path / "home.png"
    path.write_bytes(PNG)
    c = api.client()
    c.uploads.create(file=str(path))
    c.uploads.create(file=path)
    c.uploads.create(file=PNG, filename="a.png", content_type="image/png")
    with path.open("rb") as handle:
        c.uploads.create(file=handle)
    names = ("home.png", "home.png", "a.png", "upload")
    for request, name in zip(api.requests, names, strict=True):
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert f'name="file"; filename="{name}"'.encode() in request.content
        assert PNG in request.content
    assert b"Content-Type: image/png" in api.requests[2].content


def test_multipart_is_rebuilt_for_a_retry(api: MockApi) -> None:
    busy = {"error": {"code": "SERVICE_UNAVAILABLE", "message": "busy"}}
    api.on(
        "POST",
        "/uploads",
        lambda _r: httpx.Response(503, json=busy, headers={"retry-after": "1"}),
        ready,
    )
    api.client().uploads.create(file=PNG)
    assert len(api.requests) == 2 and PNG in api.requests[1].content


def test_upload_from_url_is_json(api: MockApi) -> None:
    api.on("POST", "/uploads", ready)
    api.client().uploads.create(url="https://example.com/home.png")
    assert json.loads(api.requests[0].content) == {"url": "https://example.com/home.png"}


def test_exactly_one_source_and_size_cap(api: MockApi, tmp_path: Path) -> None:
    c = api.client()
    with pytest.raises(StoreshotError):
        c.uploads.create()
    with pytest.raises(StoreshotError):
        c.uploads.create(file=PNG, url="https://example.com/a.png")
    with pytest.raises(StoreshotError) as info:
        c.uploads.create(file=io.BytesIO(b"0" * (MAX_UPLOAD_BYTES + 1)))
    assert info.value.code == "FILE_TOO_LARGE"
    big = tmp_path / "big.png"
    with big.open("wb") as handle:
        handle.truncate(MAX_UPLOAD_BYTES + 1)
    with pytest.raises(StoreshotError) as info:
        c.uploads.create(file=big)
    assert info.value.code == "FILE_TOO_LARGE"
    text: Any = io.StringIO("text")
    with pytest.raises(StoreshotError):
        c.uploads.create(file=text)
    with pytest.raises(StoreshotError):
        c.uploads.create(file=123)  # type: ignore[arg-type]
    assert api.requests == []
