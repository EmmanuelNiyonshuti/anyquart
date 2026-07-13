from __future__ import annotations

import inspect
import os
from collections.abc import AsyncIterator
from collections.abc import Callable
from collections.abc import Coroutine
from collections.abc import Generator
from collections.abc import Iterable
from collections.abc import Iterator
from functools import partial
from functools import wraps
from pathlib import Path
from typing import Any
from typing import overload
from typing import ParamSpec
from typing import TYPE_CHECKING
from typing import TypeVar

import anyio
from werkzeug.datastructures import Headers

from .typing import FilePath

if TYPE_CHECKING:
    from .wrappers.response import Response  # noqa: F401

T = TypeVar("T")
P = ParamSpec("P")


def file_path_to_path(*paths: FilePath) -> Path:
    # Flask supports bytes paths
    safe_paths: list[str | os.PathLike] = []
    for path in paths:
        if isinstance(path, bytes):
            safe_paths.append(path.decode())
        else:
            safe_paths.append(path)
    return Path(*safe_paths)


@overload
def run_sync(
    func: Callable[P, Generator[T, None, None]],
) -> Callable[P, Coroutine[None, None, AsyncIterator[T]]]: ...


@overload
def run_sync(func: Callable[P, T]) -> Callable[P, Coroutine[None, None, T]]: ...


def run_sync(func: Callable[P, Any]) -> Callable[P, Coroutine[None, None, Any]]:
    """Ensure that the sync function is run within the worker thread.

    This ensures that synchronous functions do not
    block the event loop.
    """

    @wraps(func)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        result = await anyio.to_thread.run_sync(partial(func, *args, **kwargs))
        if inspect.isgenerator(result):
            return run_sync_iterable(result)
        else:
            return result

    _wrapper._anyquart_async_wrapper = True  # type: ignore
    return _wrapper


class _StopIteration(Exception):  # noqa: N818
    pass


def _next(iterator: Iterator[T]) -> T:
    try:
        return next(iterator)
    except StopIteration as e:
        raise _StopIteration from e


def run_sync_iterable(iterable: Iterator[T]) -> AsyncIterator[T]:
    async def _gen_wrapper() -> AsyncIterator[T]:
        while True:
            try:
                yield await anyio.to_thread.run_sync(_next, iterable)
            except _StopIteration:
                return

    return _gen_wrapper()


def encode_headers(headers: Headers) -> list[tuple[bytes, bytes]]:
    return [(key.lower().encode(), value.encode()) for key, value in headers.items()]


def decode_headers(headers: Iterable[tuple[bytes, bytes]]) -> Headers:
    return Headers([(key.decode(), value.decode()) for key, value in headers])
