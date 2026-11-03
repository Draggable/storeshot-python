"""API keys (SS-026 §4.2)."""

from __future__ import annotations

from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import ApiKeyList, CreateApiKeyRequest, CreatedApiKey


class ApiKeys:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(
        self, body: CreateApiKeyRequest, /, **options: Unpack[RequestOptions]
    ) -> CreatedApiKey:
        """`POST /api-keys` (`keys:manage`). The secret is in the answer only once."""
        return cast(CreatedApiKey, self._r.call("createApiKey", json=body, options=options))

    def list(self, **options: Unpack[RequestOptions]) -> ApiKeyList:
        """`GET /api-keys`."""
        return cast(ApiKeyList, self._r.call("listApiKeys", options=options))

    def revoke(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /api-keys/{id}`."""
        self._r.call("revokeApiKey", path={"id": id}, options=options)
