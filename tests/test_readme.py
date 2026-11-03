"""The README example runs and type-checks; the method table equals the operation map."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
import readme_example
from _mock import BASE, TEST_KEY, MockApi

import storeshot
from storeshot._operation_map import EXTRA_METHODS, OPERATION_MAP, PYTHON_ONLY_METHODS

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text("utf-8")


def test_extract_rejects_a_missing_or_doubled_marker() -> None:
    with pytest.raises(ValueError):
        readme_example.extract("no marker")
    with pytest.raises(ValueError):
        readme_example.extract(f"{readme_example.MARKER}\n{readme_example.MARKER}\n")
    with pytest.raises(ValueError):
        readme_example.extract(f"{readme_example.MARKER}\n```ts\nx\n```\n")


def test_example_runs_against_the_mock(
    api: MockApi,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = readme_example.extract(README)
    (tmp_path / "home.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    api.json("POST", "/uploads", {"id": "u1", "status": "ready"}, status=201)
    api.json("POST", "/screenshot-sets", {"id": "s1", "status": "queued"}, status=202)
    done = {"id": "s1", "status": "succeeded", "images": 2, "counts": {"succeeded": 2}}
    api.json("GET", "/screenshot-sets/s1", done)
    api.on(
        "GET", "/screenshot-sets/s1/archive", lambda _r: httpx.Response(200, content=b"PK\x03\x04")
    )
    real = storeshot.Storeshot

    def fake(*args: Any, **kwargs: Any) -> Any:
        assert args == () and kwargs == {}, "the example must rely on the environment"
        return real(TEST_KEY, base_url=BASE, http_client=api.http())

    monkeypatch.setattr(storeshot, "Storeshot", fake)
    monkeypatch.chdir(tmp_path)
    exec(compile(code, "README example", "exec"), {"__name__": "__main__"})
    assert capsys.readouterr().out == "succeeded 2/2 images\n"
    assert (tmp_path / "listing.zip").read_bytes() == b"PK\x03\x04"
    sent = api.requests[1]
    assert sent.headers["idempotency-key"] and b'"uploadId":"u1"' in sent.content
    assert api.requests[-1].url.params["layout"] == "fastlane"


def test_example_is_strictly_typed(tmp_path: Path) -> None:
    code, _ = readme_example.extract(README)
    (tmp_path / "example.py").write_text(code, "utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            "--cache-dir=/dev/null",
            str(tmp_path / "example.py"),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_method_table_equals_the_maps() -> None:
    section = README.split("## Method reference", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `([a-z_.]+)`", section, re.MULTILINE)
    assert len(rows) == len(set(rows)) and rows == sorted(rows)
    assert set(rows) == {*OPERATION_MAP.values(), *EXTRA_METHODS, *PYTHON_ONLY_METHODS}


def test_no_env_assignment_lines() -> None:
    pattern = r"(?:^|[\s;'\"`(])(?:export\s+)?[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|KEY)=[^\s=]"
    assert not re.search(pattern, README, re.MULTILINE)
