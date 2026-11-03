"""Every type of the SDK (SS-026 §4.2): the contract's schemas (keys = the API's names), the
per-operation query TypedDicts, and the SDK's own dataclasses and options."""

from __future__ import annotations

from ._core.options import ClientIdentity, RequestOptions
from ._core.request import ResponseMeta
from ._errors import SdkErrorCode
from ._generated.operations import OperationId
from ._generated.schemas import *  # noqa: F403
from ._generated.schemas import __all__ as _SCHEMAS
from ._helpers.archive import ArchiveStream, DownloadedArchive
from ._helpers.files import UploadFile
from ._resources.auth import DeviceCode, DeviceCodePrompt, DevicePoll, LinkedAccount
from ._resources.screenshot_sets import ArchiveLayout

__all__ = [
    *_SCHEMAS,
    "ArchiveLayout",
    "ArchiveStream",
    "ClientIdentity",
    "DeviceCode",
    "DeviceCodePrompt",
    "DevicePoll",
    "DownloadedArchive",
    "LinkedAccount",
    "OperationId",
    "RequestOptions",
    "ResponseMeta",
    "SdkErrorCode",
    "UploadFile",
]
