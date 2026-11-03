"""One call per operation through its SDK method (the TS SDK's test/fixtures/operationCalls.ts)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ID = "00000000-0000-4000-8000-000000000001"
SET_BODY: Any = {
    "app": {"name": "Trailmate"},
    "screens": [{"input": {"uploadId": ID}}],
    "stores": [{"store": "app_store"}],
}
GENERATION_BODY: Any = {
    "inputs": [{"uploadId": ID}],
    "store": "app_store",
    "device": "app_store_1290x2796",
    "app": {"name": "Trailmate"},
}
WEBHOOK_BODY: Any = {"url": "https://example.com/hook", "events": ["generation.succeeded"]}

OPERATION_CALLS: dict[str, Callable[[Any], Any]] = {
    "addProjectItems": lambda c: c.projects.add_items(ID, {"generationIds": [ID]}),
    "cancelBillingSubscription": lambda c: c.billing.cancel_subscription(),
    "cancelGeneration": lambda c: c.generations.cancel(ID),
    "cancelScreenshotSet": lambda c: c.screenshot_sets.cancel(ID),
    "changeBillingSubscription": lambda c: c.billing.change_subscription({"plan": "pro"}),
    "completeUpload": lambda c: c.uploads.complete(ID),
    "createApiKey": lambda c: c.api_keys.create({"name": "k", "environment": "test"}),
    "createBillingCheckout": lambda c: c.billing.create_checkout({"pack": "credits_15"}),
    "createBillingPortalSession": lambda c: c.billing.create_portal_session(),
    "createBillingSubscriptionCheckout": lambda c: c.billing.create_subscription_checkout(
        {"plan": "pro"}
    ),
    "createDeviceAuthorization": lambda c: c.auth.start_device_authorization(),
    "createDeviceToken": lambda c: c.auth.poll_device_token("D" * 43),
    "createGeneration": lambda c: c.generations.create(GENERATION_BODY),
    "createPalette": lambda c: c.palettes.create({"inputs": [{"uploadId": ID}]}),
    "createProject": lambda c: c.projects.create({"name": "Trailmate"}),
    "createScreenshotSet": lambda c: c.screenshot_sets.create(SET_BODY),
    "createUpload": lambda c: c.uploads.create(file=b"\x89PNG\r\n\x1a\n", filename="a.png"),
    "createWebhook": lambda c: c.webhooks.create(WEBHOOK_BODY),
    "deleteGeneration": lambda c: c.generations.delete(ID),
    "deleteProject": lambda c: c.projects.delete(ID),
    "deleteScreenshotSet": lambda c: c.screenshot_sets.delete(ID),
    "deleteUpload": lambda c: c.uploads.delete(ID),
    "deleteWebhook": lambda c: c.webhooks.delete(ID),
    "getBillingCheckout": lambda c: c.billing.get_checkout(ID),
    "getBillingSubscription": lambda c: c.billing.get_subscription(),
    "getCredits": lambda c: c.credits.get(),
    "getGeneration": lambda c: c.generations.get(ID),
    "getHealth": lambda c: c.health(),
    "getMe": lambda c: c.me(),
    "getProject": lambda c: c.projects.get(ID),
    "getScreenshotSet": lambda c: c.screenshot_sets.get(ID),
    "getScreenshotSetArchive": lambda c: c.screenshot_sets.archive(ID),
    "getStatus": lambda c: c.status(),
    "getStoreRequirements": lambda c: c.stores.requirements("app_store"),
    "getUpload": lambda c: c.uploads.get(ID),
    "getUsage": lambda c: c.usage.get({"groupBy": "source"}),
    "getWebhook": lambda c: c.webhooks.get(ID),
    "listActivity": lambda c: c.activity.list({"limit": 5}),
    "listApiKeys": lambda c: c.api_keys.list(),
    "listBillingPacks": lambda c: c.billing.list_packs(),
    "listBillingPlans": lambda c: c.billing.list_plans(),
    "listDevices": lambda c: c.devices.list(),
    "listGenerations": lambda c: c.generations.list(),
    "listProjects": lambda c: c.projects.list(),
    "listScreenshotSets": lambda c: c.screenshot_sets.list(),
    "listStores": lambda c: c.stores.list(),
    "listUploads": lambda c: c.uploads.list(),
    "listWebhookDeliveries": lambda c: c.webhooks.list_deliveries(ID),
    "listWebhooks": lambda c: c.webhooks.list(),
    "presignUpload": lambda c: c.uploads.presign({"contentType": "image/png", "bytes": 8}),
    "removeProjectItems": lambda c: c.projects.remove_items(ID, {"generationIds": [ID]}),
    "retryScreenshotSet": lambda c: c.screenshot_sets.retry(ID),
    "revokeApiKey": lambda c: c.api_keys.revoke(ID),
    "rotateWebhookSecret": lambda c: c.webhooks.rotate_secret(ID),
    "testWebhook": lambda c: c.webhooks.test(ID),
    "uncancelBillingSubscription": lambda c: c.billing.uncancel_subscription(),
    "updateProject": lambda c: c.projects.update(ID, {"name": "n"}),
    "updateWebhook": lambda c: c.webhooks.update(ID, {"description": "d"}),
}
