# AnyQuart

Quart runs on Asyncio and when you want to run it on Trio event loop you use [quart-trio](https://github.com/pgjones/quart-trio) extension.

AnyQuart is [Quart](https://github.com/pallets/quart) running on [AnyIO](https://github.com/agronholm/anyio). It is a fork of Quart 0.20.1.



## Differences from Quart
`AnyQuart` and `Quart` are essentially the same thing. The only difference is the name and the internals(Asyncio replaced with AnyIO). This also means the testing setup changes, which is explained in the [Testing](#testing) section below.

- Works with both asyncio and Trio code via AnyIO, giving you structured concurrency out of the box.
- Uses [Anycorn](https://github.com/davidbrochart/anycorn) instead of Hypercorn as the development server.
- [aiofiles](https://github.com/Tinche/aiofiles) dropped, AnyIO's file I/O is used instead.
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) replaced by [AnyIO pytest plugin](https://anyio.readthedocs.io/en/stable/testing.html).
- Runs on Python 3.10+ .

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
Pytest requires a plugin to run asynchronous test functions and fixtures.
Quart uses pytest-asyncio, while AnyQuart uses AnyIO's pytest plugin. You will need to specify which backend your tests run on via the `anyio_backend` fixture and decorate your asynchronous tests with `@pytest.mark.anyio`.

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

Refer to the [Quart documentation](https://quart.palletsprojects.com) for more details.

## Contributing
Issues and Pull Requests are welcome.

## Contributors ✨

<details>
  <summary>See All Contributors</summary>

  <div align="center">
    <a href="https://github.com/EmmanuelNiyonshuti/anyquart/graphs/contributors?all=1">
      <img src="https://contrib.rocks/image?repo=EmmanuelNiyonshuti/anyquart"/>
    </a>
  </div>
</details>

