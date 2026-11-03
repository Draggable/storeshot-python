"""Webhook endpoints (SS-026 §4.2); signature verification lives in storeshot.webhooks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    CreateWebhookRequest,
    ListWebhookDeliveriesQuery,
    ListWebhooksQuery,
    RotateWebhookSecretRequest,
    UpdateWebhookRequest,
    Webhook,
    WebhookDelivery,
    WebhookDeliveryList,
    WebhookList,
    WebhookTestResult,
    WebhookWithSecret,
)
from .._helpers.pagination import paginate


class Webhooks:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def create(
        self, body: CreateWebhookRequest, /, **options: Unpack[RequestOptions]
    ) -> WebhookWithSecret:
        """`POST /webhooks` (`webhooks:write`). The secret is in the answer only once."""
        return cast(WebhookWithSecret, self._r.call("createWebhook", json=body, options=options))

    def list(
        self, query: ListWebhooksQuery | None = None, /, **options: Unpack[RequestOptions]
    ) -> WebhookList:
        """`GET /webhooks`."""
        return cast(WebhookList, self._r.call("listWebhooks", query=query, options=options))

    def get(self, id: str, /, **options: Unpack[RequestOptions]) -> Webhook:
        """`GET /webhooks/{id}`."""
        return cast(Webhook, self._r.call("getWebhook", path={"id": id}, options=options))

    def update(
        self, id: str, body: UpdateWebhookRequest, /, **options: Unpack[RequestOptions]
    ) -> Webhook:
        """`PATCH /webhooks/{id}`."""
        result = self._r.call("updateWebhook", path={"id": id}, json=body, options=options)
        return cast(Webhook, result)

    def delete(self, id: str, /, **options: Unpack[RequestOptions]) -> None:
        """`DELETE /webhooks/{id}`."""
        self._r.call("deleteWebhook", path={"id": id}, options=options)

    def rotate_secret(
        self,
        id: str,
        body: RotateWebhookSecretRequest | None = None,
        /,
        **options: Unpack[RequestOptions],
    ) -> WebhookWithSecret:
        """`POST /webhooks/{id}/rotate-secret`: the new secret, once."""
        result = self._r.call(
            "rotateWebhookSecret", path={"id": id}, json=body or {}, options=options
        )
        return cast(WebhookWithSecret, result)

    def test(self, id: str, /, **options: Unpack[RequestOptions]) -> WebhookTestResult:
        """`POST /webhooks/{id}/test`: sends a signed `webhook.test` event."""
        result = self._r.call("testWebhook", path={"id": id}, options=options)
        return cast(WebhookTestResult, result)

    def list_deliveries(
        self,
        id: str,
        query: ListWebhookDeliveriesQuery | None = None,
        /,
        **options: Unpack[RequestOptions],
    ) -> WebhookDeliveryList:
        """`GET /webhooks/{id}/deliveries`."""
        result = self._r.call(
            "listWebhookDeliveries", path={"id": id}, query=query, options=options
        )
        return cast(WebhookDeliveryList, result)

    def list_all_deliveries(
        self,
        id: str,
        query: ListWebhookDeliveriesQuery | None = None,
        /,
        **options: Unpack[RequestOptions],
    ) -> Iterator[WebhookDelivery]:
        """Every delivery of a webhook across pages (lazy; `limit` is the page size)."""
        pages = paginate(
            lambda q: self.list_deliveries(id, cast(ListWebhookDeliveriesQuery, q), **options),
            query,
        )
        return cast(Iterator[WebhookDelivery], pages)
