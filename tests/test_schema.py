import uuid

import psycopg
import pytest


def _insert_game(conn, **overrides):
    gid = uuid.uuid4()
    row = dict(
        id=gid, ics_uid=f"{gid}@fixturefeed", season=2026, game_type="REG",
        week=4, home_team="CLE", away_team="PIT",
        start_utc="2026-10-02T00:15:00Z", content_hash="x",
    ) | overrides
    conn.execute(
        """INSERT INTO games (id, ics_uid, season, game_type, week, home_team,
                              away_team, start_utc, content_hash)
           VALUES (%(id)s, %(ics_uid)s, %(season)s, %(game_type)s, %(week)s,
                   %(home_team)s, %(away_team)s, %(start_utc)s, %(content_hash)s)""",
        row,
    )
    return gid


def test_schema_creates_all_tables(db):
    tables = {r[0] for r in db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )}
    assert tables == {"teams", "games", "game_source_ids", "snapshots",
                      "game_changes", "feeds", "schema_migrations", "link_events"}


def test_all_32_teams_seeded(db):
    assert db.execute("SELECT count(*) FROM teams").fetchone()[0] == 32


def test_natural_key_is_unique(db):
    _insert_game(db)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _insert_game(db, week=6)  # same season/type/home/away, different week


def test_unknown_team_rejected(db):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _insert_game(db, home_team="XXX")


def test_status_limited_to_known_values(db):
    gid = _insert_game(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE games SET status = 'postponed' WHERE id = %s", (gid,))


def test_rejected_snapshot_needs_reason(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            """INSERT INTO snapshots (source, fetched_at, sha256, row_count, accepted)
               VALUES ('nflverse', now(), 'abc', 0, false)"""
        )
