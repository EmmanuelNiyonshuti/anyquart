from __future__ import annotations

import pytest
from anycorn.typing import HTTPScope
from anycorn.typing import WebsocketScope


@pytest.fixture(
    params=[
        pytest.param("asyncio", id="asyncio"),
        pytest.param("trio", id="trio"),
    ]
)
async def anyio_backend(request: pytest.FixtureRequest) -> None:
    return request.param


@pytest.fixture(name="http_scope")
def _http_scope() -> HTTPScope:
    return {
        "type": "http",
        "asgi": {},
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
        "state": {},  # type: ignore[typeddict-item]
        "extensions": {},
    }


@pytest.fixture(name="websocket_scope")
def _websocket_scope() -> WebsocketScope:
    return {
        "type": "websocket",
        "asgi": {},
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
        "state": {},  # type: ignore[typeddict-item]
        "extensions": {},
    }
