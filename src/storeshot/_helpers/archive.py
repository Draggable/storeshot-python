"""Archive downloads (SS-026 §6.5)."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

CHUNK = 65536


def read_all(response: httpx.Response) -> bytes:
    return response.read()


class ArchiveStream:
    """The archive as a stream; use it as a context manager (it owns the connection)."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def iter_bytes(self, chunk_size: int = CHUNK) -> Iterator[bytes]:
        return self._response.iter_bytes(chunk_size)

    def close(self) -> None:
        self._response.close()

    def __enter__(self) -> ArchiveStream:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


@dataclass(frozen=True)
class DownloadedArchive:
    path: str
    bytes: int


def write_response_to_file(
    response: httpx.Response, path: str | os.PathLike[str]
) -> DownloadedArchive:
    """Streams to `<path>.part`, then renames it; on any error the part file is removed."""
    target = os.fspath(path)
    part = f"{target}.part"
    written = 0
    try:
        with open(part, "wb") as handle:
            for chunk in response.iter_bytes(CHUNK):
                handle.write(chunk)
                written += len(chunk)
        os.replace(part, target)
        return DownloadedArchive(path=target, bytes=written)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(part)
        raise
