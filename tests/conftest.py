import os

import psycopg
import pytest

from fixturefeed.db import apply_schema

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
        apply_schema(conn)
        yield conn
