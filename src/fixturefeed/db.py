"""Postgres connection and migrations (psycopg 3, hand-written SQL).

Migrations are numbered files in `fixturefeed/migrations/` (0001_name.sql,
0002_name.sql, ...). Each runs once, in its own transaction, and is recorded
in `schema_migrations`. Never edit a migration that has been applied anywhere
real; add a new one.

Run:
    uv run python -m fixturefeed.db
"""

import os
import re
from importlib.resources import files

import psycopg

DEFAULT_DATABASE_URL = "postgresql:///fixturefeed"
_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_MIGRATE_LOCK_KEY = 0x46_46_4D_47  # "FFMG"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or database_url())


def migration_files() -> list[tuple[str, str]]:
    """(version, sql) for every migration, in order."""
    found = []
    for entry in files("fixturefeed").joinpath("migrations").iterdir():
        if m := _MIGRATION_NAME.match(entry.name):
            found.append((m.group(1), entry.read_text()))
    found.sort()
    versions = [v for v, _ in found]
    if len(versions) != len(set(versions)):
        raise RuntimeError(f"duplicate migration numbers: {versions}")
    return found


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations. Returns the versions applied."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATE_LOCK_KEY,))
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version    text PRIMARY KEY,
                   applied_at timestamptz NOT NULL DEFAULT now())"""
        )
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        applied = []
        for version, sql in migration_files():
            if version in done:
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied.append(version)
    return applied


if __name__ == "__main__":
    with connect() as c:
        applied = migrate(c)
    print(f"applied: {', '.join(applied)}" if applied else "database is up to date")
