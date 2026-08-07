# AnyQuart

Quart runs on Asyncio and when you want to run it on Trio event loop you use [quart-trio](https://github.com/pgjones/quart-trio) extension.

AnyQuart is [Quart](https://github.com/pallets/quart) running on [AnyIO](https://github.com/agronholm/anyio). It is a fork of Quart 0.20.1.

[![Tests](https://github.com/EmmanuelNiyonshuti/anyquart/actions/workflows/tests.yaml/badge.svg)](https://github.com/EmmanuelNiyonshuti/anyquart/actions)
[![PyPI](https://img.shields.io/pypi/v/anyquart.svg)](https://pypi.org/project/anyquart/)
[![Python](https://img.shields.io/pypi/pyversions/anyquart.svg)](https://pypi.org/project/anyquart/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![t](https://img.shields.io/badge/status-maintained-yellow.svg)

## Differences from Quart
`AnyQuart` and `Quart` are essentially the same thing. The only difference is the name and the internals(Asyncio replaced with AnyIO). This also means the testing setup changes, which is explained in the [Testing](#testing) section below.

1. Works with both asyncio and Trio code via AnyIO, giving you structured concurrency out of the box.
2. [aiofiles](https://github.com/Tinche/aiofiles) dropped, AnyIO's file I/O is used instead.
3. [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) replaced by [AnyIO pytest plugin](https://anyio.readthedocs.io/en/stable/testing.html).
4. As of 0.3.0, [Anycorn](https://github.com/davidbrochart/anycorn) is an optional dependency for the development server, while Quart installs [Hypercorn](https://hypercorn.readthedocs.io) as a required dependency for the same purpose.
5. As of 0.3.0, AnyQuart provides a Request-scoped dependency injection for route handlers.
Request handlers may mark parameters with :class:`Needs` to resolve a request-scoped value.
e.g:
    ```python
    from anyquart import Needs

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            yield session

    @app.route("/users")
    async def get_users(db: AsyncSession = Needs(get_db)) -> None:
        ...

    # Or:
    DBSession = Annotated[AsyncSession, Needs(get_db)]

    @app.route("/users")
    async def get_users(db: DBSession) -> None:
        ...

    # Tests can use `app.dependency_overrides` dictionary to replace route handler's
    # dependency with test dependency
    ```
6. Runs on Python 3.10+

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
Install an ASGI web server, pick one from [this list](https://asgi.readthedocs.io/en/latest/implementations.html), or install anyquart with Anycorn directly:
```bash
$ uv add anyquart[anycorn]
```
run the application:
```bash
$ anycorn app:app
 * [2026-08-01 11:49:46 +0200] [30809] [INFO] Running on http://127.0.0.1:8000 (CTRL + C to quit)
```
The built-in `anyquart run` command is only available on anyquart <= 0.2.1 — from 0.3.0 onward, run the ASGI server directly as shown above.

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
