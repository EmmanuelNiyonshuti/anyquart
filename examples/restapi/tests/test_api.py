import pytest


@pytest.mark.anyio
async def test_echo(test_client) -> None:
    response = await test_client.post("/echo", json={"a": "b"})
    assert (await response.get_json()) == {"extra": True, "input": {"a": "b"}}
    assert response.status_code == 200


@pytest.mark.anyio
async def test_create_todo(test_client) -> None:
    response = await test_client.post("/todos/", json={"task": "Abc", "due": None})
    assert response.status_code == 201
    assert (await response.get_json()) == {"id": 1, "task": "Abc", "due": None}
