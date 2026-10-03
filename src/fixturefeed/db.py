"""Postgres connection and schema setup (psycopg 3, hand-written SQL)."""

import os
from importlib.resources import files

import psycopg

DEFAULT_DATABASE_URL = "postgresql:///fixturefeed"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or database_url())


def apply_schema(conn: psycopg.Connection) -> None:
    """Create all tables in an empty database, in one transaction."""
    sql = files("fixturefeed").joinpath("schema.sql").read_text()
    with conn.transaction():
        conn.execute(sql)
