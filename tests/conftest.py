"""Shared pytest setup: scripts/ and tests/ importable, no STORESHOT_* variable leaks into a test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
sys.path.insert(0, str(PACKAGE_ROOT / "tests"))
# pytest's --basetemp (pyproject addopts) lives under .tmp/ (git-ignored), never in /tmp.
(PACKAGE_ROOT / ".tmp").mkdir(exist_ok=True)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("STORESHOT_API_KEY", "STORESHOT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


from _mock import MockApi  # noqa: E402

from storeshot._core import clock  # noqa: E402


@pytest.fixture
def api() -> MockApi:
    return MockApi()


class FakeClock:
    """monotonic() advances only on sleep(): every wait loop runs instantly and deterministically."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(clock, "sleep", fake.sleep)
    monkeypatch.setattr(clock, "monotonic", fake.monotonic)
    monkeypatch.setattr(clock, "random", lambda: 0.5)
    return fake
