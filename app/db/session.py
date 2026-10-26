from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings


def get_async_db_url(url: str | None = None) -> str:
    """Normalise a Postgres URL (as copied from Supabase, Heroku, ...) for SQLAlchemy + asyncpg."""
    conn = url or settings.DATABASE_URL
    if conn.startswith("postgres://"):
        conn = conn.replace("postgres://", "postgresql+asyncpg://", 1)
    elif conn.startswith("postgresql://"):
        conn = conn.replace("postgresql://", "postgresql+asyncpg://", 1)

    if conn.startswith("postgresql+asyncpg://"):
        # asyncpg takes libpq's sslmode as "ssl"
        parts = urlsplit(conn)
        query = [("ssl" if key == "sslmode" else key, val) for key, val in parse_qsl(parts.query)]
        conn = urlunsplit(parts._replace(query=urlencode(query)))
    return conn


def uses_pgbouncer(url: str) -> bool:
    if settings.DATABASE_PGBOUNCER is not None:
        return settings.DATABASE_PGBOUNCER
    # 6543 is the port of Supabase's transaction-mode connection pooler
    return url.startswith("postgresql+asyncpg://") and urlsplit(url).port == 6543


def db_schema() -> str | None:
    """The configured schema, or None for Postgres' default (public)."""
    return None if settings.DB_SCHEMA == "public" else settings.DB_SCHEMA


def create_engine(url: str | None = None) -> AsyncEngine:
    url = get_async_db_url(url)
    schema = db_schema()
    is_postgres = url.startswith("postgresql+asyncpg://")
    kwargs: dict = {}
    connect_args: dict = {}
    if uses_pgbouncer(url):
        # PgBouncer/Supavisor in transaction mode can't keep prepared statements across
        # transactions, so disable asyncpg's statement caches and let the pooler do the pooling.
        kwargs["poolclass"] = NullPool
        connect_args |= {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        }
    else:
        kwargs["pool_pre_ping"] = True
    if schema and is_postgres:
        # Only the app's schema is on the search path, so nothing can land in public by mistake
        # (session-mode poolers and direct connections keep this setting).
        connect_args["server_settings"] = {"search_path": schema}
        # Qualify every table with the schema in generated SQL too, which also works where
        # startup settings like search_path aren't kept (transaction-mode poolers).
        kwargs["execution_options"] = {"schema_translate_map": {None: schema}}
    return create_async_engine(url, connect_args=connect_args, **kwargs)


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_maker
    if _engine is None:
        _engine = create_engine()
        _session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None


def get_session() -> AsyncSession:
    get_engine()
    return _session_maker()


async def db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that provides a session per request."""
    async with get_session() as session:
        yield session


# Route parameter type for a request-scoped session: `db: DBSession`
DBSession = Annotated[AsyncSession, Depends(db_session)]
