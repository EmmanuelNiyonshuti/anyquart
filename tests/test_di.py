import time
from collections.abc import AsyncGenerator
from typing import Annotated
from typing import Any

import anyio
import pytest

from anyquart import AnyQuart
from anyquart import Needs
from anyquart import request
from anyquart import ResponseReturnValue
from anyquart.di import build_route_handler_dependency_map
from anyquart.di import rule_arguments


def test_rule_arguments() -> None:
    assert rule_arguments("/") == set()
    assert rule_arguments("/users/<int:user_id>") == {"user_id"}
    assert rule_arguments("/a/<first>/b/<path:second>") == {"first", "second"}


def test_build_route_handler_deps_default_value() -> None:
    def dummy_dep() -> str:
        return "dummy-value"

    async def handler(value: str = Needs(dummy_dep)) -> str:
        return value

    assert build_route_handler_dependency_map(handler) == {"value": dummy_dep}


def test_build_route_handler_annotated_dep() -> None:
    def dummy_dep() -> str:
        return "dummy-value"

    DummyDep = Annotated[str, Needs(dummy_dep)]  # noqa 806

    async def handler(value: DummyDep) -> str:
        return value

    assert build_route_handler_dependency_map(handler) == {"value": dummy_dep}


def test_build_route_handler_deps_map_without_deps() -> None:
    async def handler(user_id: int, value: str = "default") -> str:
        return value

    assert build_route_handler_dependency_map(handler) == {}


def test_same_path_param_name_with_dependency_name_raise_value_error(
    app: AnyQuart,
) -> None:
    async def dependency() -> str:
        return "user"

    with pytest.raises(ValueError, match="appear as URL rule converters"):

        @app.route("/users/<int:user_id>")
        async def get_user(user_id: int = Needs(dependency)) -> str:
            return "unused"


def test_name_collision_with_rule_defaults_raises(app: AnyQuart) -> None:
    async def dependency() -> str:
        return "page"

    with pytest.raises(ValueError, match="appear as URL rule converters"):

        @app.route("/book", defaults={"page": 0})
        async def get_book(page: int = Needs(dependency)) -> str:
            return "unused"


async def test_single_dependency_default_value_style(app: AnyQuart) -> None:
    async def dependency() -> str:
        return "resolved-value"

    @app.route("/")
    async def index(value: str = Needs(dependency)) -> str:
        return value

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"resolved-value" == (await response.get_data())


async def test_single_annotated_dependency(app: AnyQuart) -> None:
    def dummy_dep() -> str:
        return "dummy-value"

    DummyDep = Annotated[str, Needs(dummy_dep)]  # noqa 806

    @app.route("/")
    async def index(value: DummyDep) -> str:
        return value

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"dummy-value" == (await response.get_data())


async def test_nested_dependencies(app: AnyQuart) -> None:
    async def get_a() -> str:
        return "a"

    async def get_b(a: str = Needs(get_a)) -> str:
        return f"b({a})"

    async def get_c(b: str = Needs(get_b)) -> str:
        return f"c({b})"

    @app.route("/")
    async def index(c: str = Needs(get_c)) -> str:
        return c

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"c(b(a))" == (await response.get_data())


async def test_annotated_and_default_deps_mixed(app: AnyQuart) -> None:
    def dummy_dep() -> str:
        return "dummy-value"

    DummyDep = Annotated[str, Needs(dummy_dep)]  # noqa 806

    async def dummy_dep_two() -> str:
        return "default"

    @app.route("/")
    async def index(value: DummyDep, other: str = Needs(dummy_dep_two)) -> str:
        return f"{value}|{other}"

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"dummy-value|default" == (await response.get_data())


async def test_nested_sub_dependencies(app: AnyQuart) -> None:
    async def get_a() -> str:
        return "a"

    async def get_b(a: str = Needs(get_a)) -> str:
        return f"b({a})"

    async def get_c(b: str = Needs(get_b)) -> str:
        return f"c({b})"

    @app.route("/")
    async def index(c: str = Needs(get_c)) -> str:
        return c

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"c(b(a))" == (await response.get_data())


async def test_dependency_cached_within_request(app: AnyQuart) -> None:
    calls: list[str] = []

    async def get_user() -> str:
        calls.append("called")
        return "user-1"

    async def get_profile(user: str = Needs(get_user)) -> str:
        return f"profile-{user}"

    @app.route("/")
    async def index(
        user: str = Needs(get_user), profile: str = Needs(get_profile)
    ) -> str:
        return f"{user}|{profile}"

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"user-1|profile-user-1" == (await response.get_data())
    assert calls == ["called"]


async def test_concurrent_requests_are_isolated(app: AnyQuart) -> None:
    started: list[int] = []
    resolved: list[int] = []
    gate = anyio.Event()
    results: list[bytes | str] = []

    async def get_session() -> int:
        started.append(1)
        if len(started) == 2:
            gate.set()
        await gate.wait()
        value = len(resolved)
        resolved.append(value)
        return value

    @app.route("/")
    async def index(session: int = Needs(get_session)) -> str:
        return str(session)

    client = app.test_client()

    async def make_request() -> None:
        response = await client.get("/")
        results.append(await response.get_data())

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(make_request)
        task_group.start_soon(make_request)

    assert len(results) == 2
    assert resolved == [0, 1]
    assert sorted(results) == [b"0", b"1"]


async def test_yield_dependency_teardown_on_success(app: AnyQuart) -> None:
    teardowns: list[str] = []

    async def get_db() -> AsyncGenerator[str, None]:
        try:
            yield "connection"
        finally:
            teardowns.append("closed")

    @app.route("/")
    async def index(db: str = Needs(get_db)) -> str:
        assert db == "connection"
        assert teardowns == []
        return db

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"connection" == (await response.get_data())
    assert teardowns == ["closed"]


async def test_yield_dependency_teardown_on_handler_exception(app: AnyQuart) -> None:
    teardowns: list[str] = []

    async def get_db() -> AsyncGenerator[str, None]:
        try:
            yield "connection"
        finally:
            teardowns.append("closed")

    @app.route("/")
    async def index(db: str = Needs(get_db)) -> str:
        raise RuntimeError("handler failed")

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 500
    assert teardowns == ["closed"]


async def test_sync_dependency(app: AnyQuart) -> None:
    def get_config() -> str:
        return "sync-value"

    @app.route("/")
    async def index(config: str = Needs(get_config)) -> str:
        return config

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"sync-value" == (await response.get_data())


async def test_sync_dependency_does_not_block_event_loop(app: AnyQuart) -> None:
    order: list[str] = []

    def slow_dependency() -> str:
        time.sleep(0.15)
        order.append("dependency-finished")
        return "value"

    @app.route("/")
    async def index(value: str = Needs(slow_dependency)) -> str:
        return value

    client = app.test_client()

    async def timer() -> None:
        await anyio.sleep(0.02)
        order.append("timer-finished")

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(client.get, "/")
        task_group.start_soon(timer)

    assert order == ["timer-finished", "dependency-finished"]


async def test_sync_generator_dependency_teardown(app: AnyQuart) -> None:
    teardowns: list[str] = []

    def get_config() -> Any:
        try:
            yield "sync-generator-value"
        finally:
            teardowns.append("closed")

    @app.route("/")
    async def index(config: str = Needs(get_config)) -> str:
        return config

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 200
    assert b"sync-generator-value" == (await response.get_data())
    assert teardowns == ["closed"]


async def test_url_converter_and_needs_coexist(app: AnyQuart) -> None:
    async def get_db() -> str:
        return "database"

    @app.route("/users/<int:user_id>")
    async def index(user_id: int, db: str = Needs(get_db)) -> str:
        return f"{user_id}:{db}"

    client = app.test_client()
    response = await client.get("/users/7")
    assert response.status_code == 200
    assert b"7:database" == (await response.get_data())


async def test_dependency_error_propagates_to_error_handler(app: AnyQuart) -> None:
    async def get_broken() -> str:
        raise RuntimeError("dependency failed")

    @app.route("/")
    async def index(value: str = Needs(get_broken)) -> str:
        return value

    @app.errorhandler(RuntimeError)
    async def handle_runtime_error(error: Exception) -> ResponseReturnValue:
        return str(error), 500

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 500
    assert b"dependency failed" == (await response.get_data())


async def test_partial_teardown_when_sibling_dependency_raises(app: AnyQuart) -> None:
    teardowns: list[str] = []

    async def get_db() -> AsyncGenerator[str, None]:
        try:
            yield "connection"
        finally:
            teardowns.append("closed")

    async def get_broken() -> str:
        raise RuntimeError("dependency failed")

    @app.route("/")
    async def index(db: str = Needs(get_db), broken: str = Needs(get_broken)) -> str:
        return "unused"

    @app.errorhandler(RuntimeError)
    async def handle_runtime_error(error: Exception) -> ResponseReturnValue:
        return str(error), 500

    client = app.test_client()
    response = await client.get("/")
    assert response.status_code == 500
    assert b"dependency failed" == (await response.get_data())
    assert teardowns == ["closed"]


async def test_dependency_can_use_request_context(app: AnyQuart) -> None:
    async def get_header() -> str:
        return request.headers.get("X-Custom", "")

    @app.route("/")
    async def index(header: str = Needs(get_header)) -> str:
        return header

    client = app.test_client()
    response = await client.get("/", headers={"X-Custom": "hello"})
    assert response.status_code == 200
    assert b"hello" == (await response.get_data())


async def test_route_without_di_unaffected(app: AnyQuart) -> None:
    @app.route("/plain/<value>")
    async def index(value: str) -> str:
        return f"plain-{value}"

    client = app.test_client()
    response = await client.get("/plain/ok")
    assert response.status_code == 200
    assert b"plain-ok" == (await response.get_data())


async def test_override_only_affects_targeted_dependency(app: AnyQuart) -> None:
    async def get_user_id() -> str:
        return "real-id"

    async def get_role() -> str:
        return "real-role"

    @app.get("/")
    async def handler(
        user_id: str = Needs(get_user_id), role: str = Needs(get_role)
    ) -> dict[str, str]:
        return {"user_id": user_id, "role": role}

    async def fake_user_id() -> str:
        return "fake-id"

    client = app.test_client()
    app.dependency_overrides[get_user_id] = fake_user_id
    response = await client.get("/")

    assert response.status_code == 200
    assert await response.json == {"user_id": "fake-id", "role": "real-role"}
