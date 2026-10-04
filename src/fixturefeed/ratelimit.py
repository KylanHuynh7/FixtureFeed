"""Postgres-backed rate limit for creating or replacing feed links.

Shared across every app instance, so it holds on serverless hosting.
Client IPs are stored only as salted SHA-256 hashes.
"""

import hashlib
import os
from datetime import timedelta

import psycopg

LINKS_PER_WINDOW = 20
WINDOW = timedelta(hours=1)
# Rows older than this are deleted opportunistically.
RETENTION = timedelta(days=1)


def ip_hash(ip: str) -> str:
    salt = os.environ.get("IP_HASH_SALT", "fixturefeed")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


def allow_link_event(conn: psycopg.Connection, ip: str) -> bool:
    """Record one link event for `ip` unless it is over the limit."""
    key = ip_hash(ip)
    with conn.transaction():
        # Serialize per client so two parallel requests can't both slip under.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
        conn.execute("DELETE FROM link_events WHERE at < now() - %s", (RETENTION,))
        recent = conn.execute(
            "SELECT count(*) FROM link_events WHERE ip_hash = %s AND at > now() - %s",
            (key, WINDOW),
        ).fetchone()[0]
        if recent >= LINKS_PER_WINDOW:
            return False
        conn.execute("INSERT INTO link_events (ip_hash) VALUES (%s)", (key,))
    return True
