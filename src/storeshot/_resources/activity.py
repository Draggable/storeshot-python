"""Account activity (SS-026 §4.2)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import ActivityEntry, ActivityList, ListActivityQuery
from .._helpers.pagination import paginate


class Activity:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def list(
        self, query: ListActivityQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> ActivityList:
        """`GET /activity` (`keys:manage`)."""
        return cast(ActivityList, self._r.call("listActivity", query=query, options=options))

    def list_all(
        self, query: ListActivityQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> Iterator[ActivityEntry]:
        """Every activity entry across pages (lazy; `limit` is the page size)."""
        pages = paginate(lambda q: self.list(cast(ListActivityQuery, q), **options), query)
        return cast(Iterator[ActivityEntry], pages)
