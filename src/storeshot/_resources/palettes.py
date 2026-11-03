"""Palettes (SS-026 §4.2): free, stores nothing, so retried like a GET."""

from __future__ import annotations

from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import CreatePaletteRequest, Palette


class Palettes:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(self, body: CreatePaletteRequest, /, **options: Unpack[RequestOptions]) -> Palette:
        """`POST /palettes`: a brand palette or the dominant colour."""
        return cast(Palette, self._r.call("createPalette", json=body, options=options))
