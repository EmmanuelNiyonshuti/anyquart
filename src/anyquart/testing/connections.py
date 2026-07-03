from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Any
from typing import AnyStr
from typing import TYPE_CHECKING

from anycorn.typing import ASGIReceiveEvent
from anycorn.typing import ASGISendEvent
from anycorn.typing import HTTPScope
from anycorn.typing import WebsocketScope
from anyio import ClosedResourceError
from anyio import create_memory_object_stream
from anyio import create_task_group
from anyio.abc import TaskGroup
from werkzeug.datastructures import Headers

from ..json import dumps
from ..json import loads
from ..utils import decode_headers
from ..wrappers import Response

if TYPE_CHECKING:
    from ..app import AnyQuart  # noqa


class HTTPDisconnectError(Exception):
    pass


class WebsocketDisconnectError(Exception):
    pass


class WebsocketResponseError(Exception):
    def __init__(self, response: Response) -> None:
        super().__init__(response)
        self.response = response


class TestHTTPConnection:
    def __init__(
        self, app: AnyQuart, scope: HTTPScope, _preserve_context: bool = False
    ) -> None:
        self.app = app
        self.headers: Headers | None = None
        self.push_promises: list[tuple[str, Headers]] = []
        self.response_data = bytearray()
        self.scope = scope
        self.status_code: int | None = None
        self._preserve_context = _preserve_context
        self._server_send, self._server_receive = create_memory_object_stream[
            ASGIReceiveEvent
        ](10)
        self._client_send, self._client_receive = create_memory_object_stream[
            bytes | Exception
        ](10)
        self._tg_cm: AbstractAsyncContextManager[TaskGroup]

    async def send(self, data: bytes) -> None:
        await self._server_send.send(
            {"type": "http.request", "body": data, "more_body": True}
        )

    async def send_complete(self) -> None:
        await self._server_send.send(
            {"type": "http.request", "body": b"", "more_body": False}
        )
        await self._server_send.aclose()

    async def receive(self) -> bytes:
        data = await self._client_receive.receive()
        if isinstance(data, Exception):
            raise data
        else:
            return data

    async def disconnect(self) -> None:
        await self._server_send.send({"type": "http.disconnect"})
        await self._server_send.aclose()

    async def __aenter__(self) -> TestHTTPConnection:
        self._tg_cm = create_task_group()
        tg_entered = await self._tg_cm.__aenter__()
        tg_entered.start_soon(self.app, self.scope, self._asgi_receive, self._asgi_send)
        return self

    async def __aexit__(
        self, exc_type: type, exc_value: BaseException, tb: TracebackType
    ) -> None:
        if exc_type is not None:
            await self.disconnect()
        try:
            with self._client_receive, self._client_send:
                async for data in self._client_receive:
                    if isinstance(data, bytes):
                        self.response_data.extend(data)
                    elif not isinstance(data, HTTPDisconnectError):
                        raise data
        finally:
            await self._server_receive.aclose()
            await self._tg_cm.__aexit__(exc_type, exc_value, tb)

    async def as_response(self) -> Response:
        return self.app.response_class(
            bytes(self.response_data), self.status_code, self.headers
        )

    async def _asgi_receive(self) -> ASGIReceiveEvent:
        return await self._server_receive.receive()

    async def _asgi_send(self, message: ASGISendEvent) -> None:
        if message["type"] == "http.response.start":
            self.headers = decode_headers(message["headers"])
            self.status_code = message["status"]
        elif message["type"] == "http.response.body":
            await self._client_send.send(message["body"])
            if not message.get("more_body", False):
                await self._client_send.aclose()
        elif message["type"] == "http.response.push":
            self.push_promises.append(
                (message["path"], decode_headers(message["headers"]))
            )
        elif message["type"] == "http.disconnect":
            await self._client_send.send(HTTPDisconnectError())
            await self._client_send.aclose()


class TestWebsocketConnection:
    def __init__(self, app: AnyQuart, scope: WebsocketScope) -> None:
        self.accepted = False
        self.app = app
        self.headers: Headers | None = None
        self.response_data = bytearray()
        self.scope = scope
        self.status_code: int | None = None
        self._server_send, self._server_receive = create_memory_object_stream[
            ASGIReceiveEvent
        ](10)
        self._client_send, self._client_receive = create_memory_object_stream[
            bytes | str | Exception
        ](10)
        self._tg_cm: AbstractAsyncContextManager[TaskGroup]

    async def __aenter__(self) -> TestWebsocketConnection:
        self._tg_cm = create_task_group()
        tg_entered = await self._tg_cm.__aenter__()
        tg_entered.start_soon(self.app, self.scope, self._asgi_receive, self._asgi_send)
        return self

    async def __aexit__(
        self, exc_type: type, exc_value: BaseException, tb: TracebackType
    ) -> None:
        try:
            await self.disconnect()
        except ClosedResourceError:
            pass
        try:
            await self._tg_cm.__aexit__(None, None, None)
        finally:
            await self._client_send.aclose()
            await self._client_receive.aclose()
            await self._server_receive.aclose()

    async def receive(self) -> bytes | str:
        data = await self._client_receive.receive()
        if isinstance(data, Exception):
            raise data
        else:
            return data

    async def send(self, data: AnyStr) -> None:
        if isinstance(data, str):
            await self._server_send.send(
                {"type": "websocket.receive", "bytes": None, "text": data}
            )
        else:
            await self._server_send.send(
                {"type": "websocket.receive", "bytes": data, "text": None}
            )

    async def receive_json(self) -> Any:
        data = await self.receive()
        return loads(data)

    async def send_json(self, data: Any) -> None:
        raw = dumps(data)
        await self.send(raw)

    # close event is left like this because of static type checkers(mypy).
    # The app should send close event rather than the test client
    async def close(self, code: int) -> None: ...

    async def disconnect(self) -> None:
        await self._server_send.send({"type": "websocket.disconnect", "code": None})
        await self._server_send.aclose()

    async def _asgi_receive(self) -> ASGIReceiveEvent:
        return await self._server_receive.receive()

    async def _asgi_send(self, message: ASGISendEvent) -> None:
        if message["type"] == "websocket.accept":
            self.accepted = True
        elif message["type"] == "websocket.send":
            await self._client_send.send(message.get("bytes") or message.get("text"))
        elif message["type"] == "websocket.http.response.start":
            self.headers = decode_headers(message["headers"])
            self.status_code = message["status"]
        elif message["type"] == "websocket.http.response.body":
            self.response_data.extend(message["body"])
            if not message.get("more_body", False):
                await self._client_send.send(
                    WebsocketResponseError(
                        self.app.response_class(
                            bytes(self.response_data), self.status_code, self.headers
                        )
                    )
                )
                await self._client_send.aclose()

        elif message["type"] == "websocket.close":
            await self._client_send.send(
                WebsocketDisconnectError(message.get("code", 1000))
            )
            await self._client_send.aclose()
