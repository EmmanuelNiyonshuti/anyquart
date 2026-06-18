from __future__ import annotations

import threading
from collections.abc import Generator

import pytest

from anyquart import AnyQuart
from anyquart import request
from anyquart import ResponseReturnValue


@pytest.fixture(name="app")
def _app() -> AnyQuart:
    app = AnyQuart(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index() -> ResponseReturnValue:
        return request.method

    @app.route("/gen")
    def gen() -> ResponseReturnValue:
        def _gen() -> Generator[bytes, None, None]:
            yield b"%d" % threading.current_thread().ident
            for _ in range(2):
                yield b"b"

        return _gen(), 200

    return app


@pytest.mark.anyio
async def test_sync_request_context(app: AnyQuart) -> None:
    test_client = app.test_client()
    response = await test_client.get("/")
    assert b"GET" in (await response.get_data())
    response = await test_client.post("/")
    assert b"POST" in (await response.get_data())


@pytest.mark.anyio
async def test_sync_generator(app: AnyQuart) -> None:
    test_client = app.test_client()
    response = await test_client.get("/gen")
    result = await response.get_data()
    assert result[-2:] == b"bb"
    assert int(result[:-2]) != threading.current_thread().ident
