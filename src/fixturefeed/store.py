"""Write snapshots and their planned changes to Postgres (DECISIONS.md #18).

`ingest_snapshot` is all-or-nothing: either the snapshot is recorded together
with every game change it implies, or (on a rejected snapshot) only the
rejection is recorded and no game is touched.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import psycopg

from fixturefeed.diff import (
    GameDiff, MatchConflict, StoredGame, plan_changes, validate_snapshot,
)
from fixturefeed.sources import nflverse

# Serializes ingests so two runs can't plan against the same stale state.
_INGEST_LOCK_KEY = 0x46_46_49_4E  # "FFIN"


@dataclass
class IngestResult:
    snapshot_id: int
    accepted: bool
    reject_reason: str | None = None
    diffs: list[GameDiff] = field(default_factory=list)


def save_raw_snapshot(raw: str, fetched_at: datetime, snapshot_dir: Path) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    path = snapshot_dir / f"{nflverse.SOURCE}_{fetched_at:%Y%m%dT%H%M%SZ}_{digest[:12]}.csv"
    path.write_text(raw)
    return path


def ingest_snapshot(
    conn: psycopg.Connection, raw: str, fetched_at: datetime, season: int
) -> IngestResult:
    """Parse, validate, diff, and persist one nflverse snapshot for `season`."""
    digest = hashlib.sha256(raw.encode()).hexdigest()

    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_INGEST_LOCK_KEY,))

        try:
            incoming = nflverse.parse_games(raw, season)
        except nflverse.SnapshotError as e:
            return _reject(conn, fetched_at, digest, 0, f"parse error: {e}")

        stored = load_games(conn, season)
        reason = validate_snapshot(incoming, stored, _previous_row_count(conn))
        if reason is None:
            reason = _unknown_teams(conn, incoming)
        if reason:
            return _reject(conn, fetched_at, digest, len(incoming), reason)

        try:
            plan = plan_changes(stored, incoming, _espn_index(conn))
        except MatchConflict as e:
            return _reject(conn, fetched_at, digest, len(incoming), f"match conflict: {e}")

        snapshot_id = _insert_snapshot(conn, fetched_at, digest, len(incoming), None)
        for diff in plan.diffs:
            _write_game(conn, diff)
            _log_changes(conn, diff, snapshot_id)
        _upsert_source_ids(conn, plan.source_ids)

    return IngestResult(snapshot_id, True, None, plan.diffs)


def load_games(conn: psycopg.Connection, season: int) -> list[StoredGame]:
    rows = conn.execute(
        """SELECT id, ics_uid, season, game_type, week, home_team, away_team,
                  start_utc, time_tbd, venue, status, sequence, content_hash
           FROM games WHERE season = %s""",
        (season,),
    ).fetchall()
    return [StoredGame(*r) for r in rows]


def _espn_index(conn) -> dict:
    rows = conn.execute(
        """SELECT external_id, game_id FROM game_source_ids
           WHERE source = %s AND id_kind = 'espn'""",
        (nflverse.SOURCE,),
    )
    return dict(rows.fetchall())


def _previous_row_count(conn) -> int | None:
    row = conn.execute(
        """SELECT row_count FROM snapshots
           WHERE source = %s AND accepted ORDER BY id DESC LIMIT 1""",
        (nflverse.SOURCE,),
    ).fetchone()
    return row[0] if row else None


def _unknown_teams(conn, incoming) -> str | None:
    known = {r[0] for r in conn.execute("SELECT abbr FROM teams")}
    unknown = sorted({t for g in incoming for t in (g.home_team, g.away_team)} - known)
    return f"unknown teams: {', '.join(unknown)}" if unknown else None


def _reject(conn, fetched_at, digest, row_count, reason) -> IngestResult:
    snapshot_id = _insert_snapshot(conn, fetched_at, digest, row_count, reason)
    return IngestResult(snapshot_id, False, reason)


def _insert_snapshot(conn, fetched_at, digest, row_count, reject_reason) -> int:
    return conn.execute(
        """INSERT INTO snapshots (source, fetched_at, sha256, row_count, accepted, reject_reason)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (nflverse.SOURCE, fetched_at, digest, row_count, reject_reason is None, reject_reason),
    ).fetchone()[0]


def _write_game(conn, diff: GameDiff) -> None:
    g = diff.game
    if diff.change_type == "created":
        conn.execute(
            """INSERT INTO games (id, ics_uid, season, game_type, week, home_team,
                                  away_team, start_utc, time_tbd, venue, status,
                                  sequence, content_hash)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (g.id, g.ics_uid, g.season, g.game_type, g.week, g.home_team,
             g.away_team, g.start_utc, g.time_tbd, g.venue, g.status,
             g.sequence, g.content_hash),
        )
    else:
        conn.execute(
            """UPDATE games SET week = %s, home_team = %s, away_team = %s,
                      start_utc = %s, time_tbd = %s, venue = %s, status = %s,
                      sequence = %s, content_hash = %s, updated_at = now()
               WHERE id = %s""",
            (g.week, g.home_team, g.away_team, g.start_utc, g.time_tbd, g.venue,
             g.status, g.sequence, g.content_hash, g.id),
        )


def _log_changes(conn, diff: GameDiff, snapshot_id: int) -> None:
    """One summary row for created/cancelled/restored, one row per changed field."""
    rows = []
    if diff.change_type != "updated":
        rows.append((diff.change_type, None, None, None))
    if diff.change_type != "cancelled":  # cancellation's only field is status
        rows += [("updated", c.field, c.old, c.new) for c in diff.field_changes]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO game_changes (game_id, snapshot_id, change_type, field,
                                         old_value, new_value)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            [(diff.game.id, snapshot_id, *r) for r in rows],
        )


def _upsert_source_ids(conn, source_ids) -> None:
    # A date-based ID (e.g. pfr) can be reused by a different game after a
    # reschedule; the newest snapshot wins.
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO game_source_ids (source, id_kind, external_id, game_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (source, id_kind, external_id)
               DO UPDATE SET game_id = EXCLUDED.game_id""",
            [(nflverse.SOURCE, kind, ext, gid) for gid, kind, ext in source_ids],
        )
