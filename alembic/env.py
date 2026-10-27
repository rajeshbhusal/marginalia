import asyncio
from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

import app.db.tables  # noqa: F401 - registers every table on SQLModel.metadata
from app.db.session import create_engine, db_schema, get_async_db_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Everything, including Alembic's own version table, lives in DB_SCHEMA (default public)
SCHEMA_OPTS = {"version_table_schema": db_schema()}


def run_migrations_offline() -> None:
    """Emit the migration SQL for DATABASE_URL without connecting to it."""
    context.configure(
        url=get_async_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **SCHEMA_OPTS,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, **SCHEMA_OPTS)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against DATABASE_URL (see app/settings.py)."""
    connectable = create_engine()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
