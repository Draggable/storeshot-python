"""Package shape (SS-026 §3.5, §8)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import storeshot

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


def project() -> dict[str, Any]:
    data: dict[str, Any] = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    return data["project"]  # type: ignore[no-any-return]


def test_version_is_semver_and_aliased() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", storeshot.__version__)
    assert storeshot.SDK_VERSION == storeshot.__version__


def test_metadata() -> None:
    meta = project()
    assert meta["name"] == "storeshot"
    assert meta["requires-python"] == ">=3.10"
    assert meta["license"] == "Apache-2.0"
    assert meta["dependencies"] == [
        "httpx>=0.27,<1",
        "typing-extensions>=4.7; python_version < '3.11'",
    ]


def test_py_typed_ships() -> None:
    assert (ROOT / "src" / "storeshot" / "py.typed").is_file()
