"""Every operation of the contract, mapped to the method that calls it (SS-026 §4.2).

Values are the TS SDK's method paths in snake_case: the monorepo parity test checks that, and
tests/test_contract.py checks that every operationId of the generated table is here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

OPERATION_MAP: Final[Mapping[str, str]] = {
    "addProjectItems": "projects.add_items",
    "cancelBillingSubscription": "billing.cancel_subscription",
    "cancelGeneration": "generations.cancel",
    "cancelScreenshotSet": "screenshot_sets.cancel",
    "changeBillingSubscription": "billing.change_subscription",
    "completeUpload": "uploads.complete",
    "createApiKey": "api_keys.create",
    "createBillingCheckout": "billing.create_checkout",
    "createBillingPortalSession": "billing.create_portal_session",
    "createBillingSubscriptionCheckout": "billing.create_subscription_checkout",
    "createDeviceAuthorization": "auth.start_device_authorization",
    "createDeviceToken": "auth.poll_device_token",
    "createGeneration": "generations.create",
    "createPalette": "palettes.create",
    "createProject": "projects.create",
    "createScreenshotSet": "screenshot_sets.create",
    "createUpload": "uploads.create",
    "createWebhook": "webhooks.create",
    "deleteGeneration": "generations.delete",
    "deleteProject": "projects.delete",
    "deleteScreenshotSet": "screenshot_sets.delete",
    "deleteUpload": "uploads.delete",
    "deleteWebhook": "webhooks.delete",
    "getBillingCheckout": "billing.get_checkout",
    "getBillingSubscription": "billing.get_subscription",
    "getCredits": "credits.get",
    "getGeneration": "generations.get",
    "getHealth": "health",
    "getMe": "me",
    "getProject": "projects.get",
    "getScreenshotSet": "screenshot_sets.get",
    "getScreenshotSetArchive": "screenshot_sets.archive",
    "getStatus": "status",
    "getStoreRequirements": "stores.requirements",
    "getUpload": "uploads.get",
    "getUsage": "usage.get",
    "getWebhook": "webhooks.get",
    "listActivity": "activity.list",
    "listApiKeys": "api_keys.list",
    "listBillingPacks": "billing.list_packs",
    "listBillingPlans": "billing.list_plans",
    "listDevices": "devices.list",
    "listGenerations": "generations.list",
    "listProjects": "projects.list",
    "listScreenshotSets": "screenshot_sets.list",
    "listStores": "stores.list",
    "listUploads": "uploads.list",
    "listWebhookDeliveries": "webhooks.list_deliveries",
    "listWebhooks": "webhooks.list",
    "presignUpload": "uploads.presign",
    "removeProjectItems": "projects.remove_items",
    "retryScreenshotSet": "screenshot_sets.retry",
    "revokeApiKey": "api_keys.revoke",
    "rotateWebhookSecret": "webhooks.rotate_secret",
    "testWebhook": "webhooks.test",
    "uncancelBillingSubscription": "billing.uncancel_subscription",
    "updateProject": "projects.update",
    "updateWebhook": "webhooks.update",
}

#: Methods over an operation already listed above (the TS EXTRA_METHODS in snake_case).
EXTRA_METHODS: Final[Mapping[str, str]] = {
    "screenshot_sets.quote": "createScreenshotSet",
    "screenshot_sets.archive_stream": "getScreenshotSetArchive",
    "screenshot_sets.download_archive": "getScreenshotSetArchive",
    "wait_for_generation": "getGeneration",
    "wait_for_screenshot_set": "getScreenshotSet",
    "auth.link_account": "createDeviceToken",
}

#: Python-only helpers (SS-026 §6.6; TS follow-up F2).
PYTHON_ONLY_METHODS: Final[Mapping[str, str]] = {
    "activity.list_all": "listActivity",
    "generations.list_all": "listGenerations",
    "projects.list_all": "listProjects",
    "screenshot_sets.list_all": "listScreenshotSets",
    "uploads.list_all": "listUploads",
    "webhooks.list_all_deliveries": "listWebhookDeliveries",
}
