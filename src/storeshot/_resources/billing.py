"""Credit packs and plans (SS-026 §4.2)."""

from __future__ import annotations

from typing import cast

from .._compat import Unpack
from .._core.options import RequestOptions
from .._core.request import Requester
from .._generated.schemas import (
    BillingCheckout,
    BillingPackList,
    BillingPlanList,
    BillingPortalSession,
    BillingSubscriptionState,
    ChangeSubscriptionRequest,
    CreateBillingCheckoutRequest,
    CreatePortalSessionRequest,
    CreateSubscriptionCheckoutRequest,
)


class Billing:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def list_packs(self, **options: Unpack[RequestOptions]) -> BillingPackList:
        """`GET /billing/packs` (`billing:read`)."""
        return cast(BillingPackList, self._r.call("listBillingPacks", options=options))

    def create_checkout(
        self,
        body: CreateBillingCheckoutRequest,
        /,
        *,
        idempotency_key: str | None = None,
        **options: Unpack[RequestOptions],
    ) -> BillingCheckout:
        """`POST /billing/checkout`: a hosted checkout URL for a credit pack (auto
        Idempotency-Key)."""
        result = self._r.call(
            "createBillingCheckout", json=body, idempotency_key=idempotency_key, options=options
        )
        return cast(BillingCheckout, result)

    def get_checkout(self, id: str, /, **options: Unpack[RequestOptions]) -> BillingCheckout:
        """`GET /billing/checkouts/{id}`."""
        result = self._r.call("getBillingCheckout", path={"id": id}, options=options)
        return cast(BillingCheckout, result)

    def list_plans(self, **options: Unpack[RequestOptions]) -> BillingPlanList:
        """`GET /billing/plans`."""
        return cast(BillingPlanList, self._r.call("listBillingPlans", options=options))

    def get_subscription(self, **options: Unpack[RequestOptions]) -> BillingSubscriptionState:
        """`GET /billing/subscription`."""
        result = self._r.call("getBillingSubscription", options=options)
        return cast(BillingSubscriptionState, result)

    def create_subscription_checkout(
        self,
        body: CreateSubscriptionCheckoutRequest,
        /,
        *,
        idempotency_key: str | None = None,
        **options: Unpack[RequestOptions],
    ) -> BillingCheckout:
        """`POST /billing/subscription/checkout` (auto Idempotency-Key)."""
        result = self._r.call(
            "createBillingSubscriptionCheckout",
            json=body,
            idempotency_key=idempotency_key,
            options=options,
        )
        return cast(BillingCheckout, result)

    def change_subscription(
        self, body: ChangeSubscriptionRequest, /, **options: Unpack[RequestOptions]
    ) -> BillingSubscriptionState:
        """`POST /billing/subscription/change`."""
        result = self._r.call("changeBillingSubscription", json=body, options=options)
        return cast(BillingSubscriptionState, result)

    def cancel_subscription(self, **options: Unpack[RequestOptions]) -> BillingSubscriptionState:
        """`POST /billing/subscription/cancel` (at the end of the period)."""
        result = self._r.call("cancelBillingSubscription", options=options)
        return cast(BillingSubscriptionState, result)

    def uncancel_subscription(self, **options: Unpack[RequestOptions]) -> BillingSubscriptionState:
        """`POST /billing/subscription/uncancel`."""
        result = self._r.call("uncancelBillingSubscription", options=options)
        return cast(BillingSubscriptionState, result)

    def create_portal_session(
        self,
        body: CreatePortalSessionRequest | None = None,
        /,
        **options: Unpack[RequestOptions],
    ) -> BillingPortalSession:
        """`POST /billing/portal`: a customer portal session."""
        result = self._r.call("createBillingPortalSession", json=body or {}, options=options)
        return cast(BillingPortalSession, result)
