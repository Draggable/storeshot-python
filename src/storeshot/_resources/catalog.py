"""Devices and stores (SS-026 §4.2)."""

from __future__ import annotations

from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    DeviceList,
    ListDevicesQuery,
    StoreList,
    StoreRequirements,
    StoreTarget,
)


class Devices:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def list(
        self, query: ListDevicesQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> DeviceList:
        """`GET /devices`: the catalogue of output sizes (public)."""
        return cast(DeviceList, self._r.call("listDevices", query=query, options=options))


class Stores:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def list(self, **options: Unpack[RequestOptions]) -> StoreList:
        """`GET /stores`."""
        return cast(StoreList, self._r.call("listStores", options=options))

    def requirements(
        self, store: StoreTarget, /, **options: Unpack[RequestOptions]
    ) -> StoreRequirements:
        """`GET /stores/{store}/requirements`."""
        result = self._r.call("getStoreRequirements", path={"store": store}, options=options)
        return cast(StoreRequirements, result)
