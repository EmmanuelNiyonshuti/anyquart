import pytest
from chat.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def test_client():
    test_client = app.test_client()
    return test_client
