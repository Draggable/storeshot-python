"""Generations (SS-026 §4.2)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    CreateGenerationRequest,
    Generation,
    GenerationList,
    ListGenerationsQuery,
)
from .._helpers.pagination import paginate

#: Seconds a held request may wait at most (Prefer: wait, server cap).
MAX_WAIT_SECONDS = 60
#: Margin added to a held request's attempt timeout.
WAIT_MARGIN = 15.0


def held(wait: float | None) -> tuple[float | None, float]:
    """The Prefer: wait seconds (0–60) and the attempt timeout floor for them."""
    if wait is None:
        return None, 0.0
    seconds = min(float(MAX_WAIT_SECONDS), max(0.0, wait))
    return seconds, seconds + WAIT_MARGIN


class Generations:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(
        self,
        body: CreateGenerationRequest,
        /,
        *,
        idempotency_key: str | None = None,
        wait: float | None = None,
        **options: Unpack[RequestOptions],
    ) -> Generation:
        """`POST /generations`: one screenshot → one store image. Live keys: 1 credit. Sent with an
        Idempotency-Key (yours, or a new one reused across retries)."""
        seconds, minimum = held(wait)
        result = self._r.call(
            "createGeneration",
            json=body,
            idempotency_key=idempotency_key,
            wait=seconds,
            min_timeout=minimum,
            options=options,
        )
        return cast(Generation, result)

    def list(
        self, query: ListGenerationsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> GenerationList:
        """`GET /generations`."""
        return cast(GenerationList, self._r.call("listGenerations", query=query, options=options))

    def list_all(
        self, query: ListGenerationsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> Iterator[Generation]:
        """Every generation across pages (lazy; `limit` is the page size)."""
        pages = paginate(lambda q: self.list(cast(ListGenerationsQuery, q), **options), query)
        return cast(Iterator[Generation], pages)

    def get(
        self, id: str, /, *, wait: float | None = None, **options: Unpack[RequestOptions]
    ) -> Generation:
        """`GET /generations/{id}` (optionally held with `wait`, 0–60 s)."""
        seconds, minimum = held(wait)
        result = self._r.call(
            "getGeneration", path={"id": id}, wait=seconds, min_timeout=minimum, options=options
        )
        return cast(Generation, result)

    def cancel(self, id: str, /, **options: Unpack[RequestOptions]) -> Generation:
        """`POST /generations/{id}/cancel`."""
        return cast(Generation, self._r.call("cancelGeneration", path={"id": id}, options=options))

    def delete(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /generations/{id}`."""
        self._r.call("deleteGeneration", path={"id": id}, options=options)
