import anyio
import pytest


@pytest.mark.anyio
async def test_websocket(test_client) -> None:
    async with test_client.websocket("/ws") as test_websocket:
        send, receive = anyio.create_memory_object_stream(1)

        async def _receive_task():
            msg = await test_websocket.receive()
            await send.send(msg)

        async with anyio.create_task_group() as tg:
            tg.start_soon(_receive_task)
            await test_websocket.send("message")
            result = await receive.receive()
            tg.cancel_scope.cancel()

        assert result == "message"
