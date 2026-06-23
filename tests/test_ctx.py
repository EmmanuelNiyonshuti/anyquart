from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import Mock

import pytest
from anycorn.typing import HTTPScope
from anyio import create_task_group
from werkzeug.datastructures import Headers
from werkzeug.exceptions import BadRequest

from anyquart.app import AnyQuart
from anyquart.ctx import after_this_request
from anyquart.ctx import AppContext
from anyquart.ctx import copy_current_app_context
from anyquart.ctx import copy_current_request_context
from anyquart.ctx import copy_current_websocket_context
from anyquart.ctx import has_app_context
from anyquart.ctx import has_request_context
from anyquart.ctx import RequestContext
from anyquart.globals import g
from anyquart.globals import request
from anyquart.globals import websocket
from anyquart.routing import AnyQuartRule
from anyquart.testing import make_test_headers_path_and_query_string
from anyquart.testing import no_op_push
from anyquart.wrappers import Request


@pytest.mark.anyio
async def test_request_context_match(http_scope: HTTPScope) -> None:
    app = AnyQuart(__name__)
    url_adapter = Mock()
    rule = AnyQuartRule("/", methods={"GET"}, endpoint="index")
    url_adapter.match.return_value = (rule, {"arg": "value"})
    app.create_url_adapter = lambda *_: url_adapter  # type: ignore
    request = Request(
        "GET",
        "http",
        "/",
        b"",
        Headers([("host", "anyquart.com")]),
        "",
        "1.1",
        http_scope,
        send_push_promise=no_op_push,
    )
    async with RequestContext(app, request):
        assert request.url_rule == rule
        assert request.view_args == {"arg": "value"}


@pytest.mark.anyio
async def test_bad_request_if_websocket_route(http_scope: HTTPScope) -> None:
    app = AnyQuart(__name__)
    url_adapter = Mock()
    url_adapter.match.side_effect = BadRequest()
    app.create_url_adapter = lambda *_: url_adapter  # type: ignore
    request = Request(
        "GET",
        "http",
        "/",
        b"",
        Headers([("host", "anyquart.com")]),
        "",
        "1.1",
        http_scope,
        send_push_promise=no_op_push,
    )
    async with RequestContext(app, request):
        assert isinstance(request.routing_exception, BadRequest)


@pytest.mark.anyio
async def test_after_this_request(http_scope: HTTPScope) -> None:
    app = AnyQuart(__name__)
    headers, path, query_string = make_test_headers_path_and_query_string(app, "/")
    async with RequestContext(
        AnyQuart(__name__),
        Request(
            "GET",
            "http",
            path,
            query_string,
            headers,
            "",
            "1.1",
            http_scope,
            send_push_promise=no_op_push,
        ),
    ) as context:
        after_this_request(lambda: "hello")  # type: ignore
        assert context._after_request_functions[0]() == "hello"  # type: ignore


@pytest.mark.anyio
async def test_has_request_context(http_scope: HTTPScope) -> None:
    app = AnyQuart(__name__)
    headers, path, query_string = make_test_headers_path_and_query_string(app, "/")
    request = Request(
        "GET",
        "http",
        path,
        query_string,
        headers,
        "",
        "1.1",
        http_scope,
        send_push_promise=no_op_push,
    )
    async with RequestContext(AnyQuart(__name__), request):
        assert has_request_context() is True
        assert has_app_context() is True
    assert has_request_context() is False
    assert has_app_context() is False


@pytest.mark.anyio
async def test_has_app_context() -> None:
    async with AppContext(AnyQuart(__name__)):
        assert has_app_context() is True
    assert has_app_context() is False


@pytest.mark.anyio
async def test_copy_current_app_context() -> None:
    app = AnyQuart(__name__)

    @app.route("/")
    async def index() -> str:
        g.foo = "bar"

        @copy_current_app_context
        async def within_context() -> None:
            assert g.foo == "bar"

        async with create_task_group() as tg:
            tg.start_soon(within_context)
        return ""

    test_client = app.test_client()
    response = await test_client.get("/")
    assert response.status_code == 200


def test_copy_current_app_context_error() -> None:
    with pytest.raises(RuntimeError):
        copy_current_app_context(lambda: None)()


@pytest.mark.anyio
async def test_copy_current_request_context() -> None:
    app = AnyQuart(__name__)

    @app.route("/")
    async def index() -> str:
        @copy_current_request_context
        async def within_context() -> None:
            assert request.path == "/"

        async with create_task_group() as tg:
            tg.start_soon(within_context)
        return ""

    test_client = app.test_client()
    response = await test_client.get("/")
    assert response.status_code == 200


def test_copy_current_request_context_error() -> None:
    with pytest.raises(RuntimeError):
        copy_current_request_context(lambda: None)()


@pytest.mark.anyio
async def test_works_without_copy_current_request_context() -> None:
    app = AnyQuart(__name__)

    @app.route("/")
    async def index() -> str:
        async def within_context() -> None:
            assert request.path == "/"

        async with create_task_group() as tg:
            tg.start_soon(within_context)
        return ""

    test_client = app.test_client()
    response = await test_client.get("/")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_copy_current_websocket_context() -> None:
    app = AnyQuart(__name__)

    @app.websocket("/")
    async def index() -> None:
        @copy_current_websocket_context
        async def within_context() -> str:
            return websocket.path

        async with create_task_group() as tg:
            task_handle = tg.start_soon(within_context)
        await websocket.send(task_handle.return_value.encode())

    test_client = app.test_client()
    async with test_client.websocket("/") as test_websocket:
        data = await test_websocket.receive()
    assert cast(bytes, data) == b"/"


def test_copy_current_websocket_context_error() -> None:
    with pytest.raises(RuntimeError):
        copy_current_websocket_context(lambda: None)()
