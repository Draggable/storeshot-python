"""An httpx.MockTransport with queued answers per (METHOD, path) and a request log (SS-026 §10.1)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

TEST_KEY = "ss_test_" + "Ab3dEf6hIj9kLm2nOp5qRs8t"
LIVE_KEY = "ss_live_" + "Zy9xWv8uTs7rQp6oNm5lKj4i"
BASE = "https://api.test/v1"
Answer = Callable[[httpx.Request], httpx.Response] | Exception


class MockApi:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._answers: dict[tuple[str, str], list[Answer]] = {}
        self.fallback: Callable[[httpx.Request], httpx.Response] | None = None

    def on(self, method: str, path: str, *answers: Answer) -> MockApi:
        self._answers.setdefault((method, "/v1" + path), []).extend(answers)
        return self

    def json(
        self,
        method: str,
        path: str,
        body: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> MockApi:
        return self.on(method, path, lambda _r: httpx.Response(status, json=body, headers=headers))

    def handler(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        # The raw (still percent-encoded) path, so encoded path parameters are matched as sent.
        raw = request.url.raw_path.split(b"?", 1)[0].decode("ascii")
        queue = self._answers.get((request.method, raw))
        if not queue:
            if self.fallback is not None:
                return self.fallback(request)
            message = f"no mock for {request.method} {request.url.path}"
            return httpx.Response(
                404,
                json={"error": {"code": "NOT_FOUND", "message": message, "requestId": "req_mock"}},
            )
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        return answer(request)

    def http(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def client(self, **kwargs: Any) -> Any:
        from storeshot import Storeshot

        kwargs.setdefault("api_key", TEST_KEY)
        kwargs.setdefault("base_url", BASE)
        return Storeshot(http_client=self.http(), **kwargs)
