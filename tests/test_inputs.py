"""SS-026 §9: inputs resolve to the monorepo sources here and to package files in the mirror."""

from __future__ import annotations

import json
from pathlib import Path

import inputs
import pytest


def test_every_input_exists() -> None:
    for name in inputs.INPUTS:
        assert inputs.input_path(name).is_file(), name


def test_contract_is_the_openapi_document() -> None:
    spec = json.loads(inputs.input_path("contract").read_text("utf-8"))
    assert spec["openapi"].startswith("3.1")


def test_unknown_input() -> None:
    with pytest.raises(KeyError):
        inputs.input_path("nope")


def test_mirror_layout_uses_package_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inputs, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(inputs, "MAP_FILE", tmp_path / "mirror" / "inputs.json")
    assert inputs.input_path("contract") == tmp_path / "contract" / "openapi.json"
