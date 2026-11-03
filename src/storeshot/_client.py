"""The Storeshot client (SS-026 §4.1, §7.2, §7.3)."""

from __future__ import annotations

import math
import os
import re
import sys
from collections.abc import Callable, Mapping
from typing import Final, Literal, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from ._compat import Unpack
from ._core.headers import assert_credential, client_header, invalid, user_headers
from ._core.options import ClientIdentity, RequestOptions
from ._core.redact import mask_key
from ._core.request import Requester, RequesterConfig, ResponseMeta
from ._errors import StoreshotError
from ._generated.schemas import Generation, HealthReport, Me, ScreenshotSet, StatusReport
from ._helpers.wait import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WAIT_TIMEOUT,
    wait_for_generation,
    wait_for_screenshot_set,
)
from ._resources.activity import Activity
from ._resources.api_keys import ApiKeys
from ._resources.auth import Auth
from ._resources.billing import Billing
from ._resources.catalog import Devices, Stores
from ._resources.generations import Generations
from ._resources.palettes import Palettes
from ._resources.projects import Projects
from ._resources.screenshot_sets import ScreenshotSets
from ._resources.uploads import Uploads
from ._resources.usage import Credits, Usage
from ._resources.webhooks import Webhooks
from ._version import __version__

DEFAULT_BASE_URL: Final = "https://api.storeshot.art/v1"
DEFAULT_TIMEOUT: Final = 60.0
DEFAULT_MAX_RETRIES: Final = 2
DEFAULT_MAX_RETRY_AFTER: Final = 60.0
_LOOPBACK = re.compile(r"localhost|127(?:\.[0-9]{1,3}){3}|::1", re.ASCII)


class _FromEnv:
    def __repr__(self) -> str:
        return "FROM_ENV"


#: The default of `api_key`: read STORESHOT_API_KEY.
FROM_ENV: Final = _FromEnv()


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


def normalise_base_url(value: str) -> str:
    """https:, or http: on loopback only; no credentials, query or fragment (the CLI/TS rule)."""
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        raise invalid(f'base_url must be an absolute URL (got "{value}").') from None
    if not parts.scheme or not parts.netloc:
        raise invalid(f'base_url must be an absolute URL (got "{value}").')
    host = (parts.hostname or "").lower()
    plain_local = parts.scheme == "http" and _LOOPBACK.fullmatch(host) is not None
    if parts.scheme != "https" and not plain_local:
        raise invalid("base_url must use https: (http: only for localhost / 127.0.0.1 / [::1]).")
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        raise invalid("base_url may not contain credentials, a query or a fragment.")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, "", "")).rstrip("/")


def _number(name: str, value: float, maximum: float = math.inf) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= maximum
    ):
        raise invalid(f"{name} must be a number between 0 and {maximum:g}.")
    return float(value)


class Storeshot:
    """The Storeshot API client. One instance per API key; it holds no per-request state.

    `api_key` defaults to STORESHOT_API_KEY; `Storeshot(None)` is a key-less client for
    `client.auth.*` only (device authorization).
    """

    def __init__(
        self,
        api_key: str | None | _FromEnv = FROM_ENV,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_retry_after: float = DEFAULT_MAX_RETRY_AFTER,
        http_client: httpx.Client | None = None,
        client_identity: ClientIdentity | None = None,
        default_headers: Mapping[str, str] | None = None,
        on_response: Callable[[ResponseMeta], None] | None = None,
        environment: Literal["test", "live"] | None = None,
        dangerously_allow_browser: bool = False,
    ) -> None:
        key = _env("STORESHOT_API_KEY") if isinstance(api_key, _FromEnv) else api_key
        if key == "" or (key is None and isinstance(api_key, _FromEnv)):
            raise StoreshotError(
                "MISSING_API_KEY",
                "No API key: set STORESHOT_API_KEY (or pass api_key). Create a free test key "
                "(ss_test_…) at https://console.storeshot.art/. Never paste a key into a chat, a "
                "log or a commit.",
            )
        if key is not None:
            assert_credential(key)
        if environment is not None:
            if environment not in ("test", "live"):
                raise invalid('environment must be "test" or "live".')
            if key is None or not key.startswith(f"ss_{environment}_"):
                held = mask_key(key) if key else "no key"
                raise invalid(
                    f'environment="{environment}" needs an ss_{environment}_ key; this client '
                    f"has {held}."
                )
        if sys.platform == "emscripten" and not dangerously_allow_browser:
            raise StoreshotError(
                "BROWSER_NOT_ALLOWED",
                "Storeshot API keys are secrets: call the API from your server, not from a web "
                "page (Pyodide). Pass dangerously_allow_browser=True only if you accept that every "
                "visitor can read the key.",
            )
        self.base_url = normalise_base_url(
            base_url or _env("STORESHOT_BASE_URL") or DEFAULT_BASE_URL
        )
        self._api_key = key
        settings = RequesterConfig(
            api_key=key,
            base_url=self.base_url,
            http=http_client if http_client is not None else httpx.Client(),
            timeout=_number("timeout", timeout),
            max_retries=math.floor(_number("max_retries", max_retries, 10)),
            max_retry_after=_number("max_retry_after", max_retry_after),
            client_header=client_header(client_identity),
            user_agent=f"storeshot-sdk-python/{__version__}",
            default_headers=user_headers(default_headers),
            on_response=on_response,
        )
        self._owns_http = http_client is None
        self._http = settings.http
        self._requester = r = Requester(settings)
        self.devices = Devices(r)
        self.stores = Stores(r)
        self.api_keys = ApiKeys(r)
        self.credits = Credits(r)
        self.usage = Usage(r)
        self.uploads = Uploads(r)
        self.generations = Generations(r)
        self.screenshot_sets = ScreenshotSets(r)
        self.projects = Projects(r)
        self.palettes = Palettes(r)
        self.webhooks = Webhooks(r)
        self.activity = Activity(r)
        self.billing = Billing(r)
        #: Device authorization (RFC 8628): get an API key with your human's approval.
        self.auth = Auth(r)

    @property
    def environment(self) -> Literal["test", "live"] | None:
        """The key environment from the key prefix (None for a JWT or a key-less client)."""
        match = re.match(r"ss_(test|live)_", self._api_key or "")
        return cast(Literal["test", "live"], match.group(1)) if match else None

    def me(self, **options: Unpack[RequestOptions]) -> Me:
        """`GET /me`: the account and the credential (environment, scopes)."""
        return cast(Me, self._requester.call("getMe", options=options))

    def health(self, **options: Unpack[RequestOptions]) -> HealthReport:
        """`GET /health` (public)."""
        return cast(HealthReport, self._requester.call("getHealth", options=options))

    def status(self, **options: Unpack[RequestOptions]) -> StatusReport:
        """`GET /status` (public)."""
        return cast(StatusReport, self._requester.call("getStatus", options=options))

    def wait_for_generation(
        self,
        target: str | Generation,
        /,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Generation:
        """Returns the generation once it is succeeded, failed or canceled (long-polls with
        Prefer: wait). Raises StoreshotTimeoutError WAIT_TIMEOUT after `timeout` seconds."""
        return wait_for_generation(
            lambda id, wait: self.generations.get(id, wait=wait),
            target,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def wait_for_screenshot_set(
        self,
        target: str | ScreenshotSet,
        /,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> ScreenshotSet:
        """Returns the set once it is succeeded, partially_failed, failed or canceled."""
        return wait_for_screenshot_set(
            lambda id: self.screenshot_sets.get(id),
            target,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def close(self) -> None:
        """Closes the HTTP client the SDK created (never one you passed)."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Storeshot:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        shown = "none" if self._api_key is None else mask_key(self._api_key)
        return f"Storeshot(base_url={self.base_url}, api_key={shown})"

    __str__ = __repr__
