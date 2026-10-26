"""Helpers that keep Alembic migrations inside DB_SCHEMA and usable by the app's login role."""

from collections.abc import Sequence

from alembic import op

from app.settings import settings


def qualified(table: str) -> str:
    """A table name quoted and qualified with DB_SCHEMA, for raw SQL in migrations."""
    return f'"{settings.DB_SCHEMA}"."{table}"'


def grant_app_role(new_tables: Sequence[str] = ()) -> None:
    """Call this at the end of every migration's upgrade(), passing the tables it creates.

    On Postgres, the new tables get row-level security, so Supabase's auto-generated REST API
    can't reach them. When DB_APP_ROLE is set, that role is explicitly granted what it needs
    in DB_SCHEMA, and each new table gets a policy that lets only that role through. (A table
    owner bypasses RLS anyway; the grants and policies matter when another role owns them.)
    Nothing here touches anything outside DB_SCHEMA.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in new_tables:
        op.execute(f"ALTER TABLE {qualified(table)} ENABLE ROW LEVEL SECURITY")

    role = settings.DB_APP_ROLE
    if not role:
        return
    schema = settings.DB_SCHEMA
    # Both names are validated as plain identifiers in app/settings.py
    op.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    op.execute(
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'
    )
    op.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
    for table in new_tables:
        op.execute(
            f'CREATE POLICY marginalia_app ON {qualified(table)} TO "{role}" '
            "USING (true) WITH CHECK (true)"
        )
