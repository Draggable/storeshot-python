"""Upload inputs, buffered and capped before any request (SS-026 §6.5)."""

from __future__ import annotations

import os
from typing import BinaryIO, TypeAlias

from .._errors import StoreshotError

#: The server's upload cap (20 MiB).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UploadFile: TypeAlias = str | os.PathLike[str] | bytes | bytearray | memoryview | BinaryIO


def _too_large(size: str) -> StoreshotError:
    return StoreshotError(
        "FILE_TOO_LARGE",
        f"The file is larger than the {MAX_UPLOAD_BYTES} bytes (20 MiB) an upload may have "
        f"({size}).",
    )


def read_upload(file: UploadFile, filename: str | None) -> tuple[str, bytes]:
    """The part file name and the bytes of an upload input (checked against the cap)."""
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        size = os.stat(path).st_size
        if size > MAX_UPLOAD_BYTES:
            raise _too_large(f"{size} bytes")
        with open(path, "rb") as handle:
            data = handle.read(MAX_UPLOAD_BYTES + 1)
        name = filename or os.path.basename(path) or "upload"
    elif isinstance(file, (bytes, bytearray, memoryview)):
        data, name = bytes(file), filename or "upload"
    elif hasattr(file, "read"):
        chunk = file.read(MAX_UPLOAD_BYTES + 1)
        if not isinstance(chunk, bytes):
            raise StoreshotError(
                "INVALID_CONFIGURATION", "File objects must be opened in binary mode ('rb')."
            )
        data, name = chunk, filename or "upload"
    else:
        raise StoreshotError(
            "INVALID_CONFIGURATION",
            "file must be a path, bytes/bytearray/memoryview or a binary file object.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise _too_large(f"more than {MAX_UPLOAD_BYTES} bytes read")
    return name, data
