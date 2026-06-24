from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from anycorn.typing import ASGIReceiveEvent
from anycorn.typing import ASGISendEvent
from anycorn.typing import HTTPScope
from anycorn.typing import WebsocketScope
from anyio import create_memory_object_stream
from anyio import create_task_group
from anyio import fail_after
from werkzeug.datastructures import Headers

from anyquart import AnyQuart
from anyquart.asgi import _convert_version
from anyquart.asgi import _handle_exception
from anyquart.asgi import ASGIHTTPConnection
from anyquart.asgi import ASGIWebsocketConnection
from anyquart.utils import encode_headers


@pytest.mark.parametrize(
    "headers, expected", [([(b"host", b"anyquart")], "anyquart"), ([], "")]
)
@pytest.mark.anyio
async def test_http_1_0_host_header(headers: list, expected: str) -> None:
    app = AnyQuart(__name__)
    scope: HTTPScope = {
        "type": "http",
        "asgi": {},
        "http_version": "1.0",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 80),
        "server": None,
        "extensions": {},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIHTTPConnection(app, scope)
    request = connection._create_request_from_scope(lambda: None)  # type: ignore
    assert request.headers["host"] == expected


@pytest.mark.anyio
async def test_http_completion() -> None:
    # Ensure that the connection callable returns on completion
    app = AnyQuart(__name__)
    scope: HTTPScope = {
        "type": "http",
        "asgi": {},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "extensions": {},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIHTTPConnection(app, scope)

    send_stream, receive_stream = create_memory_object_stream[ASGIReceiveEvent](2)
    send_stream.send_nowait(
        {"type": "http.request", "body": b"", "more_body": False})

    async def receive() -> ASGIReceiveEvent:
        # This will block after returning the first and only entry
        return await receive_stream.receive()

    async def send(message: ASGISendEvent) -> None:
        pass

    # This test fails if a timeout error is raised here
    try:
        with fail_after(1):
            await connection(receive, send)
    finally:
        await send_stream.aclose()
        await receive_stream.aclose()

@pytest.mark.parametrize(
    "request_message",
    [
        {"type": "http.request", "body": b"", "more_body": False},
        {"type": "http.request", "more_body": False},
    ],
)
@pytest.mark.anyio
async def test_http_request_without_body(request_message: ASGIReceiveEvent) -> None:
    app = AnyQuart(__name__)

    scope: HTTPScope = {
        "type": "http",
        "asgi": {},
        "http_version": "1.0",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "extensions": {},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIHTTPConnection(app, scope)
    request = connection._create_request_from_scope(lambda: None)  # type: ignore

    send_stream, receive_stream = create_memory_object_stream[ASGIReceiveEvent](2)
    send_stream.send_nowait(request_message)

    async def receive() -> ASGIReceiveEvent:
        # This will block after returning the first and only entry
        return await receive_stream.receive()

    # This test fails with a timeout error if the request body is not received
    # within 1 second
    try:
        async with create_task_group() as tg:
            tg.start_soon(connection.handle_messages, request, receive)
            with fail_after(1):
                body = await request.body
            tg.cancel_scope.cancel()
    finally:
        await send_stream.aclose()
        await receive_stream.aclose()

    assert body == b""


@pytest.mark.anyio
async def test_websocket_completion() -> None:
    # Ensure that the connecion callable returns on completion
    app = AnyQuart(__name__)
    scope: WebsocketScope = {
        "type": "websocket",
        "asgi": {},
        "http_version": "1.1",
        "scheme": "wss",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIWebsocketConnection(app, scope)

    send_stream, receive_stream = create_memory_object_stream[ASGIReceiveEvent](1)
    send_stream.send_nowait({"type": "websocket.connect"})

    async def receive() -> ASGIReceiveEvent:
        # This will block after returning the first and only entry
        return await receive_stream.receive()

    async def send(message: ASGISendEvent) -> None:
        pass

    # This test fails if a timeout error is raised here
    try:
        with fail_after(1):
            await connection(receive, send)
    finally:
        await send_stream.aclose()
        await receive_stream.aclose()

def test_http_path_from_absolute_target() -> None:
    app = AnyQuart(__name__)
    scope: HTTPScope = {
        "type": "http",
        "asgi": {},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "http://anyquart/path",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "extensions": {},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIHTTPConnection(app, scope)
    request = connection._create_request_from_scope(lambda: None)  # type: ignore
    assert request.path == "/path"


@pytest.mark.parametrize(
    "path, expected",
    [("/app", "/ "), ("/", "/ "), ("/app/", "/"), ("/app/2", "/2")],
)
def test_http_path_with_root_path(path: str, expected: str) -> None:
    app = AnyQuart(__name__)
    scope: HTTPScope = {
        "type": "http",
        "asgi": {},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "/app",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "extensions": {},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIHTTPConnection(app, scope)
    request = connection._create_request_from_scope(lambda: None)  # type: ignore
    assert request.path == expected


def test_websocket_path_from_absolute_target() -> None:
    app = AnyQuart(__name__)
    scope: WebsocketScope = {
        "type": "websocket",
        "asgi": {},
        "http_version": "1.1",
        "scheme": "wss",
        "path": "ws://anyquart/path",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIWebsocketConnection(app, scope)

    send_stream, receive_stream = create_memory_object_stream[int](2)
    send_stream.close()
    receive_stream.close()
    websocket = connection._create_websocket_from_scope(lambda: None, receive_stream)  # type: ignore
    assert websocket.path == "/path"

@pytest.mark.parametrize(
    "path, expected",
    [("/app", "/ "), ("/", "/ "), ("/app/", "/"), ("/app/2", "/2")],
)
def test_websocket_path_with_root_path(path: str, expected: str) -> None:
    app = AnyQuart(__name__)
    scope: WebsocketScope = {
        "type": "websocket",
        "asgi": {},
        "http_version": "1.1",
        "scheme": "wss",
        "path": path,
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "/app",
        "headers": [(b"host", b"anyquart")],
        "client": ("127.0.0.1", 80),
        "server": None,
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
        "state": {},  # type: ignore[typeddict-item]
    }
    connection = ASGIWebsocketConnection(app, scope)
    send_stream, receive_stream = create_memory_object_stream[int](2)
    send_stream.close()
    receive_stream.close()
    websocket = connection._create_websocket_from_scope(lambda: None, receive_stream)  # type: ignore
    assert websocket.path == expected

@pytest.mark.parametrize(
    "scope, headers, subprotocol, has_headers",
    [
        ({}, Headers(), None, False),
        ({}, Headers(), "abc", False),
        ({"asgi": {"spec_version": "2.1"}}, Headers({"a": "b"}), None, True),
        ({"asgi": {"spec_version": "2.1.1"}}, Headers({"a": "b"}), None, True),
    ],
)
@pytest.mark.anyio
async def test_websocket_accept_connection(
    scope: dict, headers: Headers, subprotocol: str | None, has_headers: bool
) -> None:
    connection = ASGIWebsocketConnection(AnyQuart(__name__), scope)  # type: ignore
    mock_send = AsyncMock()
    await connection.accept_connection(mock_send, headers, subprotocol)

    if has_headers:
        mock_send.assert_called_with(
            {
                "subprotocol": subprotocol,
                "type": "websocket.accept",
                "headers": encode_headers(headers),
            }
        )
    else:
        mock_send.assert_called_with(
            {"headers": [], "subprotocol": subprotocol, "type": "websocket.accept"}
        )


@pytest.mark.anyio
async def test_websocket_accept_connection_warns(
    websocket_scope: WebsocketScope,
) -> None:
    connection = ASGIWebsocketConnection(AnyQuart(__name__), websocket_scope)

    async def mock_send(message: ASGISendEvent) -> None:
        pass

    with pytest.warns(UserWarning):
        await connection.accept_connection(mock_send, Headers({"a": "b"}), None)


def test__convert_version() -> None:
    assert _convert_version("2.1") == [2, 1]


def test_http_asgi_scope_from_request() -> None:
    app = AnyQuart(__name__)
    scope = {
        "headers": [(b"host", b"anyquart")],
        "http_version": "1.0",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "query_string": b"",
        "test_result": "PASSED",
    }
    connection = ASGIHTTPConnection(app, scope)  # type: ignore
    request = connection._create_request_from_scope(lambda: None)  # type: ignore
    assert request.scope["test_result"] == "PASSED"  # type: ignore


@pytest.mark.parametrize(
    "propagate_exceptions, testing, raises",
    [
        (True, False, False),
        (True, True, True),
        (False, True, True),
        (False, False, True),
    ],
)
@pytest.mark.anyio
async def test__handle_exception(
    propagate_exceptions: bool, testing: bool, raises: bool
) -> None:
    app = Mock()
    app.config = {}
    app.config["PROPAGATE_EXCEPTIONS"] = propagate_exceptions
    app.testing = testing

    if raises:
        with pytest.raises(ValueError):
            await _handle_exception(app, ValueError())
    else:
        await _handle_exception(app, ValueError())
