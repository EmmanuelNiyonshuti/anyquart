import pytest
from blog.main import app
from blog.main import init_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def configure_db(tmpdir):
    app.config["DATABASE"] = str(tmpdir.join("blog.db"))
    await init_db()
