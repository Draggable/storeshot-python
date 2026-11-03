# storeshot

The official Python SDK for the [Storeshot API](https://storeshot.art/docs/): turn raw app
screenshots into App Store and Google Play marketing images. Typed from the API contract (OpenAPI),
one runtime dependency (httpx), Python 3.10 or later.

> This repository is exported from Storeshot's private monorepo, where the SDK is developed and
> tested; changes land there and arrive here with each release. Issues are welcome here or at
> support@storeshot.art.

## Install

```sh
pip install storeshot
# or
uv add storeshot
```

## API key

The client reads the key from the `STORESHOT_API_KEY` environment variable (or `Storeshot(api_key)`).
Create one in the developer console (https://console.storeshot.art/):

- `ss_test_…` keys are free: everything works, but the images are sample images and no credits
  are used. Start with one.
- `ss_live_…` keys make real images and spend credits (1 per image).

Never print, log or commit a key, and never paste it into a chat. The SDK never logs the key and
masks it in `repr()`, `str()` and error messages. `Storeshot(environment="test")` refuses any key
that is not a test key before anything is sent, so a test suite cannot spend credits by accident.

No key yet? A tool can get one with its human's approval (device authorization, RFC 8628). A
client created with `Storeshot(None)` can call only `client.auth.*`; `link_account` shows your
human a console link and a code through `on_code`, waits for the approval and returns the new key
once:

```python
from storeshot import Storeshot

linked = Storeshot(None).auth.link_account(
    client_name="my-tool",
    on_code=lambda code: print(f"Open {code.verification_uri_complete}, confirm {code.user_code}."),
)
# Store linked.api_key in your secret store (never print it), then:
client = Storeshot(linked.api_key)
```

It raises `StoreshotError` `DEVICE_ACCESS_DENIED` or `DEVICE_CODE_EXPIRED` when the human denies
the request or does not answer within 10 minutes.

## Quick start

From one raw screenshot (`home.png`) to an App Store listing in fastlane's folder layout:

<!-- sdk-readme-example -->

```python
from storeshot import Storeshot

storeshot = Storeshot()  # reads STORESHOT_API_KEY
upload = storeshot.uploads.create(file="home.png")
created = storeshot.screenshot_sets.create(
    {
        "app": {"name": "Trailmate"},
        "screens": [{"input": {"uploadId": upload["id"]}, "caption": "Find every trail"}],
        "stores": [{"store": "app_store"}],
    }
)
done = storeshot.wait_for_screenshot_set(created)
print(done["status"], f"{done['counts']['succeeded']}/{done['images']} images")
storeshot.screenshot_sets.download_archive(done["id"], "listing.zip", layout="fastlane")
```

Unzip `listing.zip` in your project root: fastlane `deliver` reads `fastlane/screenshots/`. With a
live key, ask for the price first: `storeshot.screenshot_sets.quote(body)` returns `images`,
`credits` and `sufficient` and creates nothing. For a single image use
`storeshot.generations.create({"inputs": [{"uploadId": upload["id"]}], "store": "app_store",
"device": "app_store_1290x2796", "app": {"name": "Trailmate"}})`; `storeshot.devices.list()`
lists the sizes.

## Typing

Requests and answers are plain dicts whose keys are the API's own names (`uploadId`, `nextCursor`),
typed as `TypedDict`s from `storeshot.types` (`Generation`, `ScreenshotSet`,
`CreateScreenshotSetRequest`, …): your editor completes the keys and mypy or pyright check them.
They match the [API reference](https://storeshot.art/docs/api/) one to one. Only SDK options and
values the SDK builds itself (`LinkedAccount`, `ResponseMeta`, `DownloadedArchive`) use snake_case.

## Waiting

Generations and screenshot sets are asynchronous: a create returns `queued` at once.

```python
generation = storeshot.wait_for_generation(created_generation)  # or its id
if generation["status"] == "succeeded":
    print(generation["result"]["image"]["url"])

finished = storeshot.wait_for_screenshot_set(set_id, timeout=15 * 60)
```

- `wait_for_generation` long-polls with `Prefer: wait` (the server holds each request up to 60 s).
- `wait_for_screenshot_set` polls every 3 s (`poll_interval`).
- Both return the final resource, also when it `failed`, was `canceled` or (sets)
  `partially_failed`: check `status`. They raise `StoreshotTimeoutError` (`WAIT_TIMEOUT`) after
  `timeout` seconds (default 600).
- Prefer webhooks (below) for long-running work in servers.

## Uploads

```python
storeshot.uploads.create(file="screens/home.png")  # a path (str or pathlib.Path)
storeshot.uploads.create(file=data, filename="home.png")  # bytes, bytearray or memoryview
with open("home.png", "rb") as handle:
    storeshot.uploads.create(file=handle)  # a binary file object
storeshot.uploads.create(url="https://example.com/home.png")  # the server fetches it
```

PNG, JPEG or WebP, at most 20 MiB (checked before anything is sent) and 50 megapixels. Uploads are
deleted after 30 days. Reference an upload by `id` in generations and sets of the same key
environment (test or live).

## Downloads

```python
data = storeshot.screenshot_sets.archive(set_id)  # bytes
with storeshot.screenshot_sets.archive_stream(set_id) as stream:
    for chunk in stream.iter_bytes():
        ...
storeshot.screenshot_sets.download_archive(set_id, "listing.zip", layout="fastlane")
```

`download_archive` writes `listing.zip.part` and renames it when complete, so a failed download
never leaves a partial file. Image URLs in `generation["result"]` are signed for 15 minutes: get
the generation again for fresh ones.

## Pagination

```python
page = storeshot.generations.list({"status": "succeeded", "limit": 50})  # one page
for generation in storeshot.generations.list_all({"status": "succeeded", "limit": 50}):
    print(generation["id"])  # every page, fetched lazily
```

`list()` returns one page (`data`, `nextCursor`); `list_all()` follows the cursors on demand, so
`itertools.islice` stops early. Uploads, generations, screenshot sets, projects, activity and
webhook deliveries (`webhooks.list_all_deliveries(id)`) have it.

## Errors

Every failure is a `StoreshotError` (subclasses `StoreshotConnectionError`,
`StoreshotTimeoutError`, `StoreshotWebhookError`):

```python
from storeshot import StoreshotError

try:
    storeshot.screenshot_sets.create(body)
except StoreshotError as error:
    if error.code == "INSUFFICIENT_CREDITS":
        print(f"Not enough credits: top up at {(error.details or {}).get('topUpUrl')}")
    else:
        raise
```

| Attribute             | Meaning                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `status`              | HTTP status (0 when there was no response)                                                                                             |
| `code`                | API error code (`ERROR_CODES`, e.g. `INVALID_INPUT`, `RATE_LIMITED`) or an SDK code (`CONNECTION_ERROR`, `TIMEOUT`, `WAIT_TIMEOUT`, …) |
| `message`             | Human-readable, safe to show                                                                                                           |
| `request_id`          | Quote it when asking support@storeshot.art for help                                                                                    |
| `details`             | Code-specific data (`topUpUrl`, `requiredCredits`, `issues`, …)                                                                        |
| `doc_url`             | Documentation of the code                                                                                                              |
| `retry_after_seconds` | From `Retry-After` (429 and busy 503 answers)                                                                                          |

## Retries and timeouts

- `timeout` (default 60 s) bounds each network operation of an attempt (connecting, every read,
  every write); archive downloads default to 300 s.
- `max_retries` (default 2) retries with capped exponential backoff and jitter:
  - `429` and busy `503` answers with `Retry-After`, for every request: the server refused them
    before doing anything. A `Retry-After` longer than `max_retry_after` (default 60 s, e.g. the
    daily generation cap) is not waited for: you get the error with `retry_after_seconds`.
  - Other `5xx`, network errors and timeouts only where repeating is safe: `GET`, creates sent
    with an `Idempotency-Key`, quotes and palettes. Other writes (uploads, webhooks, projects,
    deletes, …) are never repeated blindly; the error says the request may have been processed.
- Per call: `timeout`, `max_retries`, `request_id`, `headers` and `on_response`
  (`storeshot.me(request_id="build-42")`).
- `on_response` (client option or per call) receives a `ResponseMeta` with `request_id`,
  `rate_limit`, `rate_limit_policy`, `idempotent_replayed` and the headers of every response.

## Idempotency

`generations.create`, `screenshot_sets.create`, `billing.create_checkout` and
`billing.create_subscription_checkout` always send an `Idempotency-Key`: a new UUID per call,
reused across that call's retries, so a retry never creates or charges twice. To make re-running a
script safe too, pass your own stable key:

```python
storeshot.screenshot_sets.create(body, idempotency_key="trailmate-release-2.4")
```

The same key with the same body returns the original resource; with a different body it is
`409 IDEMPOTENCY_CONFLICT`.

## Webhooks

Register an `https://` endpoint with `storeshot.webhooks.create({"url": url, "events": [...]})`
(the `whsec_…` secret is returned once), then verify every delivery against the **raw** body:

```python
from flask import Flask, request
from storeshot import StoreshotWebhookError, construct_webhook_event

app = Flask(__name__)
SECRET = "…"  # your whsec_ secret, from your secret store


@app.post("/hooks/storeshot")
def storeshot_hook() -> tuple[str, int]:
    try:
        event = construct_webhook_event(
            request.get_data(),  # the raw bytes, not parsed JSON
            request.headers.get("Storeshot-Signature"),
            SECRET,
        )
    except StoreshotWebhookError:
        return "", 400
    # Deduplicate on event["id"], then handle event["type"] / event["data"].
    return "", 204
```

With FastAPI or Starlette, pass `await request.body()`. `verify_webhook_signature(...)` returns a
`bool` instead of raising. The rules ([webhooks guide](https://storeshot.art/docs/webhooks/)):
`v1` is HMAC-SHA256 over `<t>.<raw body>`, any `v1` may match (two during a secret rotation),
compared in constant time; `t` must be within 5 minutes (`tolerance_seconds`). Pass
`[new_secret, old_secret]` while you roll your own configuration.

## Test mode

With an `ss_test_…` key everything works like live (validation, uploads, queue, statuses,
idempotency, archives, webhooks to test webhooks) but no credits are used and no image model runs:
each result is a sample image of exactly the requested size. Test results are deleted after 30
days. Test and live are separate: a test key only sees test uploads, generations and webhooks.
`storeshot.me()["credential"]["environment"]` reports it.

## Async frameworks

The client is synchronous (an async client is planned). In asyncio code, run calls in a thread:

```python
import asyncio

me = await asyncio.to_thread(storeshot.me)
```

## Options

- `base_url` (or `STORESHOT_BASE_URL`): `https:`, or `http:` on localhost only. The key is sent
  wherever it points.
- `http_client`: your own `httpx.Client` (proxies, TLS settings). The SDK never closes it; it must
  not carry its own auth. Redirects are never followed.
- `default_headers`, `on_response`, and `client_identity={"surface": "cli", "name": "my-tool@1.0"}`
  to label your tool's usage (`X-Storeshot-Client`, default `api/storeshot-sdk-python@<version>`).
- `with Storeshot() as storeshot:` (or `storeshot.close()`) closes the connection pool.
- Pyodide/browser pages are refused (`BROWSER_NOT_ALLOWED`): every visitor could read the key.
  `dangerously_allow_browser=True` exists for internal tools only.

## Method reference

Every API operation has exactly one method; every method takes keyword options last.

| Method                                 | Endpoint                              | Notes                    |
| -------------------------------------- | ------------------------------------- | ------------------------ |
| `activity.list`                        | `GET /activity`                       |                          |
| `activity.list_all`                    | `GET /activity`                       | every page (Python only) |
| `api_keys.create`                      | `POST /api-keys`                      |                          |
| `api_keys.list`                        | `GET /api-keys`                       |                          |
| `api_keys.revoke`                      | `DELETE /api-keys/{id}`               |                          |
| `auth.link_account`                    | `POST /auth/device/token`             | whole device flow        |
| `auth.poll_device_token`               | `POST /auth/device/token`             | no API key needed        |
| `auth.start_device_authorization`      | `POST /auth/device`                   | no API key needed        |
| `billing.cancel_subscription`          | `POST /billing/subscription/cancel`   |                          |
| `billing.change_subscription`          | `POST /billing/subscription/change`   |                          |
| `billing.create_checkout`              | `POST /billing/checkout`              | auto Idempotency-Key     |
| `billing.create_portal_session`        | `POST /billing/portal`                |                          |
| `billing.create_subscription_checkout` | `POST /billing/subscription/checkout` | auto Idempotency-Key     |
| `billing.get_checkout`                 | `GET /billing/checkouts/{id}`         |                          |
| `billing.get_subscription`             | `GET /billing/subscription`           |                          |
| `billing.list_packs`                   | `GET /billing/packs`                  |                          |
| `billing.list_plans`                   | `GET /billing/plans`                  |                          |
| `billing.uncancel_subscription`        | `POST /billing/subscription/uncancel` |                          |
| `credits.get`                          | `GET /credits`                        |                          |
| `devices.list`                         | `GET /devices`                        |                          |
| `generations.cancel`                   | `POST /generations/{id}/cancel`       |                          |
| `generations.create`                   | `POST /generations`                   | auto Idempotency-Key     |
| `generations.delete`                   | `DELETE /generations/{id}`            |                          |
| `generations.get`                      | `GET /generations/{id}`               |                          |
| `generations.list`                     | `GET /generations`                    |                          |
| `generations.list_all`                 | `GET /generations`                    | every page (Python only) |
| `health`                               | `GET /health`                         |                          |
| `me`                                   | `GET /me`                             |                          |
| `palettes.create`                      | `POST /palettes`                      |                          |
| `projects.add_items`                   | `POST /projects/{id}/items`           |                          |
| `projects.create`                      | `POST /projects`                      |                          |
| `projects.delete`                      | `DELETE /projects/{id}`               |                          |
| `projects.get`                         | `GET /projects/{id}`                  |                          |
| `projects.list`                        | `GET /projects`                       |                          |
| `projects.list_all`                    | `GET /projects`                       | every page (Python only) |
| `projects.remove_items`                | `POST /projects/{id}/items/remove`    |                          |
| `projects.update`                      | `PATCH /projects/{id}`                |                          |
| `screenshot_sets.archive`              | `GET /screenshot-sets/{id}/archive`   |                          |
| `screenshot_sets.archive_stream`       | `GET /screenshot-sets/{id}/archive`   |                          |
| `screenshot_sets.cancel`               | `POST /screenshot-sets/{id}/cancel`   |                          |
| `screenshot_sets.create`               | `POST /screenshot-sets`               | auto Idempotency-Key     |
| `screenshot_sets.delete`               | `DELETE /screenshot-sets/{id}`        |                          |
| `screenshot_sets.download_archive`     | `GET /screenshot-sets/{id}/archive`   |                          |
| `screenshot_sets.get`                  | `GET /screenshot-sets/{id}`           |                          |
| `screenshot_sets.list`                 | `GET /screenshot-sets`                |                          |
| `screenshot_sets.list_all`             | `GET /screenshot-sets`                | every page (Python only) |
| `screenshot_sets.quote`                | `POST /screenshot-sets?dryRun=true`   | free, creates nothing    |
| `screenshot_sets.retry`                | `POST /screenshot-sets/{id}/retry`    |                          |
| `status`                               | `GET /status`                         |                          |
| `stores.list`                          | `GET /stores`                         |                          |
| `stores.requirements`                  | `GET /stores/{store}/requirements`    |                          |
| `uploads.complete`                     | `POST /uploads/{id}/complete`         |                          |
| `uploads.create`                       | `POST /uploads`                       |                          |
| `uploads.delete`                       | `DELETE /uploads/{id}`                |                          |
| `uploads.get`                          | `GET /uploads/{id}`                   |                          |
| `uploads.list`                         | `GET /uploads`                        |                          |
| `uploads.list_all`                     | `GET /uploads`                        | every page (Python only) |
| `uploads.presign`                      | `POST /uploads/presign`               |                          |
| `usage.get`                            | `GET /usage`                          |                          |
| `wait_for_generation`                  | `GET /generations/{id}`               |                          |
| `wait_for_screenshot_set`              | `GET /screenshot-sets/{id}`           |                          |
| `webhooks.create`                      | `POST /webhooks`                      |                          |
| `webhooks.delete`                      | `DELETE /webhooks/{id}`               |                          |
| `webhooks.get`                         | `GET /webhooks/{id}`                  |                          |
| `webhooks.list`                        | `GET /webhooks`                       |                          |
| `webhooks.list_all_deliveries`         | `GET /webhooks/{id}/deliveries`       | every page (Python only) |
| `webhooks.list_deliveries`             | `GET /webhooks/{id}/deliveries`       |                          |
| `webhooks.rotate_secret`               | `POST /webhooks/{id}/rotate-secret`   |                          |
| `webhooks.test`                        | `POST /webhooks/{id}/test`            |                          |
| `webhooks.update`                      | `PATCH /webhooks/{id}`                |                          |

## Versioning

`storeshot.__version__` is the package version (0.x until 1.0.0; a 0.x minor may change the
surface). `storeshot.CONTRACT_VERSION` is the API contract the types were generated from (today
1.17.0); the API only changes additively within a major version, so a newer API keeps working with
this SDK. See `CHANGELOG.md`.

Licensed under the Apache License 2.0 (`LICENSE`, `NOTICE`).
