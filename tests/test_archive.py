"""Archives (SS-026 §6.5)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from _mock import MockApi

from storeshot import StoreshotConnectionError

ZIP = b"PK\x03\x04" + b"x" * 200_000


def zip_answer(_r: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=ZIP, headers={"content-type": "application/zip"})


def test_archive_bytes_and_layout(api: MockApi) -> None:
    api.on("GET", "/screenshot-sets/s1/archive", zip_answer)
    assert api.client().screenshot_sets.archive("s1", layout="fastlane") == ZIP
    req = api.requests[0]
    assert req.url.params["layout"] == "fastlane" and req.headers["accept"] == "application/zip"


def test_archive_stream(api: MockApi) -> None:
    api.on("GET", "/screenshot-sets/s1/archive", zip_answer)
    with api.client().screenshot_sets.archive_stream("s1") as stream:
        assert b"".join(stream.iter_bytes()) == ZIP


def test_download_archive_writes_via_part(api: MockApi, tmp_path: Path) -> None:
    api.on("GET", "/screenshot-sets/s1/archive", zip_answer)
    target = tmp_path / "listing.zip"
    done = api.client().screenshot_sets.download_archive("s1", target)
    assert done.path == str(target) and done.bytes == len(ZIP) and target.read_bytes() == ZIP
    assert not (tmp_path / "listing.zip.part").exists()


def test_failed_download_leaves_nothing(api: MockApi, tmp_path: Path) -> None:
    def broken(_r: httpx.Request) -> httpx.Response:
        def chunks() -> Iterator[bytes]:
            yield b"PK"
            raise httpx.ReadError("reset")

        return httpx.Response(200, content=chunks())

    api.on("GET", "/screenshot-sets/s1/archive", broken)
    with pytest.raises(StoreshotConnectionError):
        api.client(max_retries=0).screenshot_sets.download_archive("s1", tmp_path / "x.zip")
    assert list(tmp_path.iterdir()) == []


def test_quote_is_read_only_and_create_is_keyed(api: MockApi) -> None:
    api.json("POST", "/screenshot-sets", {"dryRun": True})
    c = api.client()
    body: Any = {"app": {"name": "a"}, "screens": [], "stores": []}
    c.screenshot_sets.quote(body)
    c.screenshot_sets.create(body, idempotency_key="release-2.4")
    assert api.requests[0].url.params["dryRun"] == "true"
    assert "idempotency-key" not in api.requests[0].headers
    assert api.requests[1].headers["idempotency-key"] == "release-2.4"
