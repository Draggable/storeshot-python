"""Device authorization, RFC 8628 (SS-026 §6.7; the TS SDK's resources/auth.ts).

No API key is needed: create the client with `Storeshot(None)`. Nothing here logs the codes or the
key.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from .._compat import Unpack
from .._core import clock
from .._core.options import RequestOptions
from .._core.request import OAuthError, Requester, ResponseMeta
from .._errors import StoreshotError
from .._generated.schemas import DeviceAuthorization, DeviceToken

#: RFC 8628 §3.4.
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_TERMINAL = {
    "access_denied": ("DEVICE_ACCESS_DENIED", "The request was denied."),
    "expired_token": ("DEVICE_CODE_EXPIRED", "The device code expired before it was approved."),
    "invalid_grant": ("DEVICE_INVALID_GRANT", "Unknown or already used device code."),
}


@dataclass(frozen=True)
class DeviceCode:
    #: Secret: pass it to poll_device_token, never show it.
    device_code: str = field(repr=False)
    user_code: str
    verification_uri: str
    #: The console page with the code filled in: the link to give your human.
    verification_uri_complete: str
    #: Seconds until the codes expire.
    expires_in: int
    #: Seconds to wait between polls.
    interval: int


@dataclass(frozen=True)
class DeviceCodePrompt:
    """What `link_account` shows your human through `on_code`."""

    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int


@dataclass(frozen=True)
class LinkedAccount:
    #: The new API key (shown once: store it, never log it).
    api_key: str = field(repr=False)
    key_id: str
    scopes: tuple[str, ...]
    environment: Literal["live", "test"]


@dataclass(frozen=True)
class DevicePoll:
    status: Literal["approved", "authorization_pending", "slow_down"]
    account: LinkedAccount | None = None
    retry_after_seconds: int | None = None


class Auth:
    def __init__(self, requester: Requester) -> None:
        self._r = requester

    def start_device_authorization(
        self,
        *,
        client_name: str | None = None,
        scopes: Sequence[str] | None = None,
        environment: Literal["live", "test"] | None = None,
        **options: Unpack[RequestOptions],
    ) -> DeviceCode:
        """`POST /auth/device`: a user code for your human and a device code to poll with."""
        body: dict[str, str] = {}
        if client_name is not None:
            body["client_name"] = client_name
        if scopes is not None:
            body["scope"] = " ".join(scopes)
        if environment is not None:
            body["environment"] = environment
        answer = self._r.call(
            "createDeviceAuthorization", anonymous=True, json=body, options=options
        )
        r = cast(DeviceAuthorization, answer)
        return DeviceCode(
            device_code=r["device_code"],
            user_code=r["user_code"],
            verification_uri=r["verification_uri"],
            verification_uri_complete=r["verification_uri_complete"],
            expires_in=r["expires_in"],
            interval=r["interval"],
        )

    def poll_device_token(
        self, device_code: str, /, **options: Unpack[RequestOptions]
    ) -> DevicePoll:
        """`POST /auth/device/token`, once. Raises DEVICE_ACCESS_DENIED, DEVICE_CODE_EXPIRED or
        DEVICE_INVALID_GRANT when polling must stop."""
        seen: list[int | None] = [None]
        user_hook = options.get("on_response")

        def hook(meta: ResponseMeta) -> None:
            seen[0] = meta.retry_after_seconds
            if user_hook is not None:
                user_hook(meta)

        opts: RequestOptions = {**options, "on_response": hook}
        result = self._r.call(
            "createDeviceToken",
            anonymous=True,
            oauth_errors=True,
            json={"grant_type": DEVICE_GRANT_TYPE, "device_code": device_code},
            options=opts,
        )
        if isinstance(result, OAuthError):
            if result.error == "authorization_pending":
                return DevicePoll("authorization_pending")
            if result.error == "slow_down":
                return DevicePoll("slow_down", retry_after_seconds=seen[0])
            fallback = ("UNEXPECTED_RESPONSE", f"Device authorization failed: {result.error}.")
            code, message = _TERMINAL.get(result.error, fallback)
            raise StoreshotError(
                code,
                result.error_description or message,
                status=400,
                operation_id="createDeviceToken",
                details={"error": result.error},
            )
        token = cast(DeviceToken, result)
        scope = token["scope"]
        account = LinkedAccount(
            api_key=token["access_token"],
            key_id=token["key_id"],
            scopes=tuple(scope.split(" ")) if scope else (),
            environment=token["environment"],
        )
        return DevicePoll("approved", account=account)

    def link_account(
        self,
        *,
        on_code: Callable[[DeviceCodePrompt], object],
        client_name: str | None = None,
        scopes: Sequence[str] | None = None,
        environment: Literal["live", "test"] | None = None,
    ) -> LinkedAccount:
        """The whole flow: start, show the code through on_code, poll every interval (+5 s after
        each slow_down, at least Retry-After) until approved, and return the new key. Raises
        DEVICE_ACCESS_DENIED or DEVICE_CODE_EXPIRED otherwise."""
        started = self.start_device_authorization(
            client_name=client_name, scopes=scopes, environment=environment
        )
        on_code(
            DeviceCodePrompt(
                user_code=started.user_code,
                verification_uri=started.verification_uri,
                verification_uri_complete=started.verification_uri_complete,
                expires_in=started.expires_in,
            )
        )
        deadline = clock.monotonic() + started.expires_in
        interval = wait = started.interval
        while True:
            clock.sleep(wait)
            if clock.monotonic() > deadline:
                raise StoreshotError(
                    "DEVICE_CODE_EXPIRED",
                    _TERMINAL["expired_token"][1],
                    operation_id="createDeviceToken",
                )
            poll = self.poll_device_token(started.device_code)
            if poll.account is not None:
                return poll.account
            if poll.status == "slow_down":
                # RFC 8628 §3.5: +5 s for this and every later poll; at least the server's Retry-After.
                interval += 5
                wait = max(interval, poll.retry_after_seconds or 0)
            else:
                wait = interval
