"""Screenshot sets and their archives (SS-026 §4.2, §6.5)."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any, Literal, TypeAlias, cast

import httpx

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    CreateScreenshotSetRequest,
    ListScreenshotSetsQuery,
    RetriedScreenshotSet,
    RetryScreenshotSetRequest,
    ScreenshotSet,
    ScreenshotSetList,
    ScreenshotSetQuote,
)
from .._helpers.archive import ArchiveStream, DownloadedArchive, read_all, write_response_to_file
from .._helpers.pagination import paginate

#: Default attempt timeout of archive downloads (they stream a whole ZIP).
ARCHIVE_TIMEOUT = 300.0
#: `store` (default): <store>/<device>/<NN>.png; `fastlane`: the deliver/supply folders.
ArchiveLayout: TypeAlias = Literal["store", "fastlane"]


class ScreenshotSets:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(
        self,
        body: CreateScreenshotSetRequest,
        /,
        *,
        idempotency_key: str | None = None,
        **options: Unpack[RequestOptions],
    ) -> ScreenshotSet:
        """`POST /screenshot-sets`: every screen on every device of one or both stores. Live keys:
        1 credit per image, charged at once. Sent with an Idempotency-Key."""
        result = self._r.call(
            "createScreenshotSet", json=body, idempotency_key=idempotency_key, options=options
        )
        return cast(ScreenshotSet, result)

    def quote(
        self, body: CreateScreenshotSetRequest, /, **options: Unpack[RequestOptions]
    ) -> ScreenshotSetQuote:
        """`POST /screenshot-sets?dryRun=true`: what `create` would make and charge. Free."""
        result = self._r.call(
            "createScreenshotSet",
            json=body,
            query={"dryRun": "true"},
            read_only=True,
            options=options,
        )
        return cast(ScreenshotSetQuote, result)

    def list(
        self, query: ListScreenshotSetsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> ScreenshotSetList:
        """`GET /screenshot-sets`."""
        result = self._r.call("listScreenshotSets", query=query, options=options)
        return cast(ScreenshotSetList, result)

    def list_all(
        self, query: ListScreenshotSetsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> Iterator[ScreenshotSet]:
        """Every screenshot set across pages (lazy; `limit` is the page size)."""
        pages = paginate(lambda q: self.list(cast(ListScreenshotSetsQuery, q), **options), query)
        return cast(Iterator[ScreenshotSet], pages)

    def get(self, id: str, /, **options: Unpack[RequestOptions]) -> ScreenshotSet:
        """`GET /screenshot-sets/{id}`."""
        result = self._r.call("getScreenshotSet", path={"id": id}, options=options)
        return cast(ScreenshotSet, result)

    def retry(
        self,
        id: str,
        body: RetryScreenshotSetRequest | None = None,
        /,
        **options: Unpack[RequestOptions],
    ) -> RetriedScreenshotSet:
        """`POST /screenshot-sets/{id}/retry`: new images for failed or canceled slots only."""
        result = self._r.call(
            "retryScreenshotSet", path={"id": id}, json=body or {}, options=options
        )
        return cast(RetriedScreenshotSet, result)

    def cancel(self, id: str, /, **options: Unpack[RequestOptions]) -> ScreenshotSet:
        """`POST /screenshot-sets/{id}/cancel`."""
        result = self._r.call("cancelScreenshotSet", path={"id": id}, options=options)
        return cast(ScreenshotSet, result)

    def delete(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /screenshot-sets/{id}`."""
        self._r.call("deleteScreenshotSet", path={"id": id}, options=options)

    def archive(
        self,
        id: str,
        /,
        *,
        layout: ArchiveLayout | None = None,
        **options: Unpack[RequestOptions],
    ) -> bytes:
        """`GET /screenshot-sets/{id}/archive` as bytes."""
        return cast(bytes, self._download(id, layout, options, read_all))

    def archive_stream(
        self,
        id: str,
        /,
        *,
        layout: ArchiveLayout | None = None,
        **options: Unpack[RequestOptions],
    ) -> ArchiveStream:
        """The archive as a stream (use `with`; the timeout bounds each network read)."""
        stream = self._download(id, layout, options, ArchiveStream, keep_open=True)
        return cast(ArchiveStream, stream)

    def download_archive(
        self,
        id: str,
        path: str | os.PathLike[str],
        /,
        *,
        layout: ArchiveLayout | None = None,
        **options: Unpack[RequestOptions],
    ) -> DownloadedArchive:
        """Streams the archive to `path` via `<path>.part`; nothing is left there on failure."""
        written = self._download(
            id, layout, options, lambda response: write_response_to_file(response, path)
        )
        return cast(DownloadedArchive, written)

    def _download(
        self,
        id: str,
        layout: ArchiveLayout | None,
        options: RequestOptions,
        raw: Callable[[httpx.Response], Any],
        keep_open: bool = False,
    ) -> Any:
        return self._r.call(
            "getScreenshotSetArchive",
            path={"id": id},
            query={"layout": layout},
            accept="application/zip",
            min_timeout=0.0 if "timeout" in options else ARCHIVE_TIMEOUT,
            raw=raw,
            keep_open=keep_open,
            options=options,
        )
