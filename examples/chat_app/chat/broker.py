from collections.abc import AsyncGenerator

import anyio
from anyio.abc import ObjectSendStream


class Broker:
    def __init__(self) -> None:
        self.connections: set[ObjectSendStream[str]] = set()

    async def publish(self, message: str) -> None:
        for connection in self.connections:
            await connection.send(message)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        send_stream, receive_stream = anyio.create_memory_object_stream(
            max_buffer_size=10
        )
        self.connections.add(send_stream)
        try:
            async with receive_stream:
                async for message in receive_stream:
                    yield message
        finally:
            self.connections.discard(send_stream)
