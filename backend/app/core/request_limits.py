"""Small ASGI request-body bounds for structured Admin mutation payloads."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AdminBusinessPayloadLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = 16_384) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._is_business_mutation(scope):
            await self.app(scope, receive, send)
            return

        content_length = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"content-length"),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._too_large(send)
                    return
            except ValueError:
                await self._too_large(send)
                return

        body_parts: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            part = message.get("body", b"")
            total += len(part)
            if total > self.max_bytes:
                await self._too_large(send)
                return
            body_parts.append(part)
            if not message.get("more_body", False):
                break

        body = b"".join(body_parts)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    def _is_business_mutation(scope: Scope) -> bool:
        if scope.get("type") != "http":
            return False
        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        return (method == "POST" and path == "/admin/businesses") or (
            method == "PATCH"
            and path.startswith("/admin/businesses/")
            and path.count("/") == 3
        )

    async def _too_large(self, send: Send) -> None:
        body = (
            b'{"error":{"code":"ADMIN_REQUEST_TOO_LARGE",'
            b'"message":"Business payload exceeds 16 KiB"}}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store, private"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
