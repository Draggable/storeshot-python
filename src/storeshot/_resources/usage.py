"""Credits and usage (SS-026 §4.2)."""

from __future__ import annotations

from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import CreditBalances, GetUsageQuery, UsageReport


class Credits:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def get(self, **options: Unpack[RequestOptions]) -> CreditBalances:
        """`GET /credits` (`usage:read`)."""
        return cast(CreditBalances, self._r.call("getCredits", options=options))


class Usage:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def get(
        self, query: GetUsageQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> UsageReport:
        """`GET /usage` (`usage:read`)."""
        return cast(UsageReport, self._r.call("getUsage", query=query, options=options))
