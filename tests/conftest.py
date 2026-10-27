import os
import tempfile

# Configure the app before anything imports app.settings. Tests never call a real LLM:
# the fake provider is deterministic and needs no API key.
_tmp_dir = tempfile.mkdtemp(prefix="marginalia-tests-")
os.environ["DATABASE_URL"] = (
    os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_tmp_dir}/test.db"
)
os.environ["LLM_PROVIDER"] = "fake"
os.environ["LLM_MODEL"] = "fake-tutor-1"
os.environ["LLM_CACHE"] = "false"
os.environ["FAKE_LLM_DELAY"] = "0"

import pytest  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import app.db.tables  # noqa: E402, F401
from app.db.session import dispose_engine, get_engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def database():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await dispose_engine()


@pytest.fixture
def fake_llm():
    """A fresh fake provider for one test; its `requests` list records every call."""
    from app.llm import set_llm
    from app.llm.providers.fake import FakeProvider

    provider = FakeProvider()
    set_llm(provider)
    yield provider
    set_llm(None)


@pytest.fixture
async def client(fake_llm):
    import httpx

    from app import jobs
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await jobs.drain()
