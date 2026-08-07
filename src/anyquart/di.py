from __future__ import annotations

import inspect
import re
import typing
import weakref
from collections.abc import AsyncGenerator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Generator
from dataclasses import dataclass
from functools import partial
from typing import Any

from anyio import CancelScope
from anyio import to_thread

if typing.TYPE_CHECKING:
    from .app import AnyQuart


# Matches the converter portions of a URL rule so that we can extract the
# variable names (e.g. ``<int:user_id>`` yields ``user_id``).
_rule_variable_re = re.compile(
    r"<(?:(?P<converter>[a-zA-Z_][a-zA-Z0-9_]*)(?:\([^>]*\))?:)?"
    r"(?P<variable>[a-zA-Z_][a-zA-Z0-9_]*)>"
)
_NO_VALUE = object()

_dependency_map_cache: weakref.WeakKeyDictionary[
    Callable[..., Any], dict[str, Callable[..., Any]]
] = weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class _Needs:
    """Mark a handler or dependency parameter as a request-scoped dependency.

    Arguments:
        dependency: The callable that produces the value for the marked
            parameter.
    """

    dependency: Callable[..., Any]


def Needs(dependency: Callable[..., Any]) -> Any:  # noqa 802
    return _Needs(dependency=dependency)


def build_route_handler_dependency_map(
    func: Callable[..., Any],
) -> dict[str, Callable[..., Any]]:
    """
    Build route handler dependency map(a dictionary)
        i.e:``{parameter_name: dependency_func}``

    Any handler or dependency parameter whose default value is a
    :class:`Needs` instance, or whose (evaluated) annotation is an
    :class:`Annotated` alias containing a :class:`Needs` marker, is included.

    Arguments:
        func: route handler or dependency function
    Returns:
        A dictionary mapping parameter names to their dependency callables.
    Raises:
        ValueError: if a parameter is marked as a dependency but also appears
            as a URL rule converter (or a rule ``default``) on the same route.
    """
    try:
        cached = _dependency_map_cache[func]
    except (KeyError, TypeError):
        cached = None
    if cached is not None:
        return cached

    result: dict[str, Callable[..., Any]] = {}
    signature = inspect.signature(func)

    try:
        hints = typing.get_type_hints(func, include_extras=True)
    except (NameError, TypeError, AttributeError):
        hints = {}

    for name, parameter in signature.parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        default = parameter.default
        if isinstance(default, _Needs):
            result[name] = default.dependency
            continue

        marker = _marker_from_annotation(hints.get(name, parameter.annotation))
        if marker is not None:
            result[name] = marker.dependency

    try:
        _dependency_map_cache[func] = result
    except TypeError:
        pass
    return result


def rule_arguments(rule: str) -> set[str]:
    """
    Get a set of url converter variables
    present in a url path(a Url Rule in flask lingo).
    Arguments:
        rule: a url path
    Returns:
        A set of URL converter variable names present in ``rule``.
    """
    return {match.group("variable") for match in _rule_variable_re.finditer(rule)}


def check_name_conflicts(
    view_func: Callable[..., Any], rule: str, defaults: dict[str, Any] | None = None
) -> None:
    """
    A handler parameter cannot be both a ``Needs`` dependency injected value
    and a URL rule converter (or a rule ``default``) on the same route.
    e.g:
        ```
        def dep() -> str:
            return "user"

        @app.route("/<int:user_id>")
        async def get_user(user_id: str = Needs(dep)) -> dict[str, Any]:
            ...
        ```
    Arguments:
        view_func: route handler
        rule: Url Path
        defaults:Url default values for the route, if any
    Raises:
        ValueError: if a parameter is marked as a dependency but also appears
            as a URL rule converter (or a rule ``default``) on the same route.
    """
    retval = set(build_route_handler_dependency_map(view_func))
    same_name = retval & (rule_arguments(rule) | set((defaults or {}).keys()))
    if same_name:
        raise ValueError(
            "Parameter name(s) "
            f"{', '.join(sorted(same_name))!r} in the view function for rule "
            f"{rule!r} are marked as Needs dependencies but also appear as URL "
            "rule converters (or defaults) on the same route. Please, Rename either "
            "the dependency parameter or the URL converter."
        )


async def invoke_with_di(
    app: AnyQuart, func: Callable[..., Any], view_args: dict[str, Any] | None
) -> Any:
    """
    Invoke the ``func`` resolving any of its dependency injected parameters.

    When ``func`` declares no dependencies this is exactly equivalent to
    ``await app.ensure_async(func)(**view_args)`` so non-injected routes carry
    no extra overhead.
    """
    if not build_route_handler_dependency_map(func):
        return await app.ensure_async(func)(**dict(view_args or {}))

    resolver = _Resolver(app)
    kwargs = await resolver.resolve(func, view_args)
    try:
        return await app.ensure_async(func)(**kwargs)
    finally:
        await resolver.run_teardown()


class _Resolver:
    """
    Resolves a dependency tree for a single request.

    A resolver instance is created per request and holds that request's cache
    of resolved values plus its generator teardowns, guaranteeing that two
    concurrent requests never share or leak dependency state.
    """

    def __init__(self, app: AnyQuart) -> None:
        self._app = app
        self._values: dict[Callable[..., Any], Any] = {}
        self._teardowns: list[Callable[[], Awaitable[None]]] = []

    async def resolve(
        self, func: Callable[..., Any], supplied: dict[str, Any] | None
    ) -> dict[str, Any]:
        try:
            return await self._resolve(func, supplied)
        except BaseException:
            await self.run_teardown()
            raise

    async def _resolve(
        self, func: Callable[..., Any], supplied: dict[str, Any] | None
    ) -> dict[str, Any]:
        kw = dict(supplied or {})
        for name, dependency in build_route_handler_dependency_map(func).items():
            if name in kw:
                raise ValueError(
                    f"Dependency parameter {name!r} on {func!r} was supplied a "
                    "value twice."
                )
            kw[name] = await self._resolve_dependency(dependency)
        return kw

    async def _resolve_dependency(self, dependency: Callable[..., Any]) -> Any:
        dependency = self._app.dependency_overrides.get(dependency, dependency)
        cached = self._values.get(dependency, _NO_VALUE)

        if cached is not _NO_VALUE:
            return cached

        sub_values = await self._resolve(dependency, None)

        if inspect.isasyncgenfunction(dependency):
            agen: AsyncGenerator[Any, None] = dependency(**sub_values)
            value = await anext(agen)
            self._teardowns.append(partial(_close, agen))
        elif inspect.isgeneratorfunction(dependency):
            gen: Generator[Any, None, None] = dependency(**sub_values)
            value = await to_thread.run_sync(partial(next, gen))
            self._teardowns.append(partial(_after_yield, gen))
        else:
            value = await self._app.ensure_async(dependency)(**sub_values)

        self._values[dependency] = value
        return value

    async def run_teardown(self) -> None:
        with CancelScope(shield=True):
            for teardown in reversed(self._teardowns):
                await teardown()
        self._teardowns.clear()


def _marker_from_annotation(annotation: Any) -> _Needs | None:
    if annotation is inspect.Parameter.empty:
        return None
    if typing.get_origin(annotation) is not typing.Annotated:
        return None
    for metadata in typing.get_args(annotation)[1:]:
        if isinstance(metadata, _Needs):
            return metadata
    return None


async def _close(asyncgen: AsyncGenerator[Any, None]) -> None:
    await asyncgen.aclose()


async def _after_yield(generator: Generator[Any, None, None]) -> None:
    await to_thread.run_sync(_after_yield_sync, generator)


def _after_yield_sync(generator: Generator[Any, None, None]) -> None:
    for _ in generator:
        pass
