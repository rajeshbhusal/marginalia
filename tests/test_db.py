from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.db.base_model import TZDateTime
from app.db.session import get_async_db_url, uses_pgbouncer


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@db:5432/m", "postgresql+asyncpg://u:p@db:5432/m"),
        ("postgresql://u:p@db:5432/m", "postgresql+asyncpg://u:p@db:5432/m"),
        (
            "postgresql://u:p@db.supabase.co:5432/postgres?sslmode=require",
            "postgresql+asyncpg://u:p@db.supabase.co:5432/postgres?ssl=require",
        ),
        ("sqlite+aiosqlite:///tmp/x.db", "sqlite+aiosqlite:///tmp/x.db"),
    ],
)
def test_database_urls_are_normalised_for_asyncpg(url, expected):
    assert get_async_db_url(url) == expected


def test_supabase_transaction_pooler_uses_pgbouncer_mode():
    pooler = "postgresql+asyncpg://u:p@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
    direct = "postgresql+asyncpg://u:p@db.abc.supabase.co:5432/postgres"
    assert uses_pgbouncer(pooler)
    assert not uses_pgbouncer(direct)


def test_tz_datetime_stores_utc_and_returns_aware_values():
    column = TZDateTime()
    local = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=5)))
    stored = column.process_bind_param(local, None)
    assert stored == datetime(2026, 1, 1, 7, tzinfo=UTC)
    naive = datetime(2026, 1, 1, 7)
    assert column.process_result_value(naive, None).tzinfo == UTC


def test_engine_targets_the_configured_schema(monkeypatch):
    from app.db.session import create_engine
    from app.settings import settings

    monkeypatch.setattr(settings, "DB_SCHEMA", "marginalia")
    engine = create_engine("postgresql://u:p@db:5432/m")
    assert engine.sync_engine.get_execution_options()["schema_translate_map"] == {
        None: "marginalia"
    }
    monkeypatch.setattr(settings, "DB_SCHEMA", "public")
    engine = create_engine("postgresql://u:p@db:5432/m")
    assert "schema_translate_map" not in engine.sync_engine.get_execution_options()


def test_schema_and_role_names_must_be_plain_identifiers():
    from pydantic import ValidationError

    from app.settings import Settings

    with pytest.raises(ValidationError):
        Settings(DB_SCHEMA='x"; drop table course; --')
    assert Settings(DB_SCHEMA="marginalia", DB_APP_ROLE="marginalia_app").DB_SCHEMA


def test_every_migration_grants_the_app_role():
    from pathlib import Path

    versions = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    for migration in versions.glob("*.py"):
        assert "grant_app_role(" in migration.read_text(), migration.name
