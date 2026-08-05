from __future__ import annotations

import pytest

from anyquart import AnyQuart
from anyquart.typing import HTTPScope
from anyquart.typing import WebSocketScope


@pytest.fixture(
    params=[
        pytest.param("asyncio", id="asyncio"),
        pytest.param("trio", id="trio"),
    ]
)
def anyio_backend(request: pytest.FixtureRequest) -> None:
    return request.param


@pytest.fixture
def app() -> AnyQuart:
    return AnyQuart(__name__)


@pytest.fixture(name="http_scope")
def _http_scope() -> HTTPScope:
    return {
        "type": "http",
        "asgi": {"spec_version": "2.0", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"a=b",
        "root_path": "",
        "headers": [
            (b"User-Agent", b"Anycorn"),
            (b"X-Anycorn", b"Anycorn"),
            (b"Referer", b"anycorn"),
        ],
        "client": ("127.0.0.1", 80),
        "server": None,
        "state": {},
        "extensions": {},
    }


@pytest.fixture(name="websocket_scope")
def _websocket_scope() -> WebSocketScope:
    return {
        "type": "websocket",
        "asgi": {"spec_version": "2.0", "version": "3.0"},
        "http_version": "1.1",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"a=b",
        "root_path": "",
        "headers": [
            (b"User-Agent", b"Anycorn"),
            (b"X-Anycorn", b"Anycorn"),
            (b"Referer", b"anycorn"),
        ],
        "client": ("127.0.0.1", 80),
        "server": None,
        "subprotocols": [],
        "state": {},
        "extensions": {},
    }
