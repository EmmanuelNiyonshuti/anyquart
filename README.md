# AnyQuart

Quart runs on Asyncio and when you want to run it on Trio event loop you use [quart-trio](https://github.com/pgjones/quart-trio) extension.

AnyQuart is [Quart](https://github.com/pallets/quart) running on [AnyIO](https://github.com/agronholm/anyio). It is a fork of Quart 0.20.1.

All credit for Quart goes to the [Pallets](https://palletsprojects.com) team.

## Usage
You will have to replace `quart` with `anyquart` and `Quart` with `AnyQuart`.

Install from PyPI using an installer such as pip. Requires Python 3.10+.

```
$ pip install anyquart
```

Save the following as `app.py`.

```python
from anyquart import AnyQuart, websocket, render_template

app = AnyQuart(__name__)

@app.route("/")
async def hello():
    return await render_template("index.html")

@app.route("/api")
async def json():
    return {"hello": "world"}

@app.websocket("/ws")
async def ws():
    while True:
        await websocket.send("hello")
        await websocket.send_json({"hello": "world"})
```

```
$ anyquart run
 * Running on http://127.0.0.1:5000 (CTRL + C to quit)
```

# Testing
Pytest does not natively support async test functions hence we need an async framework for async tests and fixtures.
Quart uses pytest-asyncio, here we use AnyIO's pytest plugin. You will need to specify which backend your tests run on via the `anyio_backend` fixture and decorate your asynchronous tests with `@pytest.mark.anyio`.

```python
import pytest

from app import app

@pytest.fixture()
def anyio_backend():
    return "trio" # you can replace with "asyncio"

@pytest.fixture()
def test_client():
    return app.test_client()

@pytest.mark.anyio
async def test_do_something(test_client) -> None:
    response = await test_client.get("/")
    assert response.status_code == 200
    assert await response.json == {"hello": "world"}

```

## Differences from Quart
- Uses [Anycorn](https://github.com/davidbrochart/anycorn) instead of Hypercorn as the development server
- Works with both asyncio and Trio via AnyIO
- Uses AnyIO's file I/O instead of aiofiles
- AnyIO primitives work freely in route handlers, giving you structured concurrency out of the box
- Tests need `@pytest.mark.anyio` and the `anyio_backend` fixture instead of pytest-asyncio

Refer to the [Quart documentation](https://quart.palletsprojects.com) for more details.