from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import TYPE_CHECKING

from anycorn.typing import ASGIReceiveEvent
from anycorn.typing import ASGISendEvent
from anycorn.typing import LifespanScope
from anyio import create_memory_object_stream
from anyio import create_task_group
from anyio import Event
from anyio import fail_after
from anyio.abc import TaskGroup

from ..typing import TestClientProtocol

if TYPE_CHECKING:
    from ..app import AnyQuart  # noqa

DEFAULT_TIMEOUT = 6


class LifespanError(Exception):
    pass


class TestApp:
    def __init__(
        self,
        app: AnyQuart,
        startup_timeout: int = DEFAULT_TIMEOUT,
        shutdown_timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.app = app
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self._startup = Event()
        self._shutdown = Event()
        self._app_send_stream, self._app_receive_stream = create_memory_object_stream[
            ASGIReceiveEvent
        ](10)
        self._tg_cm: AbstractAsyncContextManager[TaskGroup]

    def test_client(self) -> TestClientProtocol:
        return self.app.test_client()

    async def __aenter__(self) -> TestApp:
        self._tg_cm = create_task_group()
        entered_tg = await self._tg_cm.__aenter__()
        scope: LifespanScope = {
            "type": "lifespan",
            "asgi": {"spec_version": "2.0"},
            "state": {},
        }
        entered_tg.start_soon(self.app, scope, self._asgi_receive, self._asgi_send)
        await self._app_send_stream.send({"type": "lifespan.startup"})
        with fail_after(self.startup_timeout):
            await self._startup.wait()
        return self

    async def __aexit__(
        self, exc_type: type, exc_value: BaseException, tb: TracebackType
    ) -> None:
        await self._app_send_stream.send({"type": "lifespan.shutdown"})
        with fail_after(self.shutdown_timeout):
            await self._shutdown.wait()

        await self._app_send_stream.aclose()
        await self._tg_cm.__aexit__(exc_type, exc_value, tb)
        await self._app_receive_stream.aclose()

    # since the `TestAppProtocol` defines startup and shutdown methods
    # startup and shutdown are added here for static type checkers only
    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def _asgi_receive(self) -> ASGIReceiveEvent:
        return await self._app_receive_stream.receive()

    async def _asgi_send(self, message: ASGISendEvent) -> None:
        if message["type"] == "lifespan.startup.complete":
            self._startup.set()
        elif message["type"] == "lifespan.shutdown.complete":
            self._shutdown.set()
        elif message["type"] == "lifespan.startup.failed":
            self._startup.set()
            raise LifespanError(f"Error during startup {message['message']}")
        elif message["type"] == "lifespan.shutdown.failed":
            self._shutdown.set()
            raise LifespanError(f"Error during shutdown {message['message']}")
