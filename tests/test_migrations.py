from fixturefeed.db import database_url, migrate, migration_files


def test_migrations_numbered_and_ordered():
    versions = [v for v, _ in migration_files()]
    assert versions == sorted(versions)
    assert versions[0] == "0001"


def test_migrate_records_versions_and_is_idempotent(db):
    # The db fixture already migrated; running again applies nothing.
    assert migrate(db) == []
    recorded = [r[0] for r in db.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert recorded == [v for v, _ in migration_files()]


def test_database_url_ignores_pasted_whitespace(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://h/db?sslmode=require\n")
    assert database_url() == "postgresql://h/db?sslmode=require"
