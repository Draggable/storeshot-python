"""Uploads (SS-026 §4.2, §6.5)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .._compat import Unpack
from .._core.headers import invalid
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    ListUploadsQuery,
    PresignedUpload,
    PresignUploadRequest,
    Upload,
    UploadList,
)
from .._helpers.files import UploadFile, read_upload
from .._helpers.pagination import paginate


class Uploads:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(
        self,
        *,
        file: UploadFile | None = None,
        url: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        **options: Unpack[RequestOptions],
    ) -> Upload:
        """`POST /uploads`: a file (path, bytes or binary file object; one multipart part) or a URL
        the server fetches. PNG, JPEG or WebP, at most 20 MiB (checked before anything is sent)."""
        if (file is None) == (url is None):
            raise invalid("Pass exactly one of file= or url=.")
        if url is not None:
            return cast(Upload, self._r.call("createUpload", json={"url": url}, options=options))
        assert file is not None
        name, data = read_upload(file, filename)
        part = (name, data, content_type or "application/octet-stream")
        return cast(Upload, self._r.call("createUpload", form=part, options=options))

    def list(
        self, query: ListUploadsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> UploadList:
        """`GET /uploads`."""
        return cast(UploadList, self._r.call("listUploads", query=query, options=options))

    def list_all(
        self, query: ListUploadsQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> Iterator[Upload]:
        """Every upload across pages (lazy; `limit` is the page size)."""
        pages = paginate(lambda q: self.list(cast(ListUploadsQuery, q), **options), query)
        return cast(Iterator[Upload], pages)

    def presign(
        self, body: PresignUploadRequest, /, **options: Unpack[RequestOptions]
    ) -> PresignedUpload:
        """`POST /uploads/presign`: then PUT the file to `url` and call `complete(id)`."""
        return cast(PresignedUpload, self._r.call("presignUpload", json=body, options=options))

    def complete(self, id: str, /, **options: Unpack[RequestOptions]) -> Upload:
        """`POST /uploads/{id}/complete`."""
        return cast(Upload, self._r.call("completeUpload", path={"id": id}, options=options))

    def get(self, id: str, /, **options: Unpack[RequestOptions]) -> Upload:
        """`GET /uploads/{id}`."""
        return cast(Upload, self._r.call("getUpload", path={"id": id}, options=options))

    def delete(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /uploads/{id}`."""
        self._r.call("deleteUpload", path={"id": id}, options=options)
