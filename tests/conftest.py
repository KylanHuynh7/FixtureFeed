import os

import psycopg
import pytest

from fixturefeed.db import migrate

TEST_DATABASE_URL = os.environ.get(
    "FIXTUREFEED_TEST_DATABASE_URL", "postgresql:///fixturefeed_test"
)


@pytest.fixture
def db():
    """A connection to a freshly rebuilt test database.

    Drops and recreates the public schema, so it must never point at real data.
    """
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.commit()
        migrate(conn)
        yield conn


@pytest.fixture
def client(db):
    """Web test client on the test database, preloaded with the real snapshot."""
    from fastapi.testclient import TestClient

    from fixturefeed.store import ingest_snapshot
    from fixturefeed.web import app, get_conn, link_limiter
    from tests.test_store import REAL, T0

    link_limiter._hits.clear()
    ingest_snapshot(db, REAL, T0, 2026)
    app.dependency_overrides[get_conn] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
