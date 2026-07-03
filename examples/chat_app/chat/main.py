import anyio

from anyquart import AnyQuart
from anyquart import render_template
from anyquart import websocket
from chat.broker import Broker

app = AnyQuart(__name__)
broker = Broker()


@app.get("/")
async def index():
    return await render_template("index.html")


async def _receive() -> None:
    while True:
        message = await websocket.receive()
        await broker.publish(message)


@app.websocket("/ws")
async def ws() -> None:
    async with anyio.create_task_group() as tg:
        tg.start_soon(_receive)
        async for message in broker.subscribe():
            await websocket.send(message)
        tg.cancel_scope.cancel()
