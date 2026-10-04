import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fixturefeed import store
from fixturefeed.store import ingest_snapshot, load_games, save_raw_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
REAL = (FIXTURES / "nflverse_2026_snapshot_2026-10-03.csv").read_text()
T0 = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)


def edit_csv(text, target, **changes):
    """HAND-EDITED copy of a snapshot: change one row, or drop it if changes is None."""
    reader = csv.DictReader(io.StringIO(text))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        if row["game_id"] == target:
            if changes.get("drop"):
                continue
            row.update(changes)
        writer.writerow(row)
    return out.getvalue()


def scalar(db, sql, *params):
    return db.execute(sql, params).fetchone()[0]


def game_by_key(db, home, away):
    return db.execute(
        "SELECT id, ics_uid, week, sequence, status FROM games WHERE home_team = %s AND away_team = %s",
        (home, away),
    ).fetchone()


def test_first_ingest_creates_all_games(db):
    result = ingest_snapshot(db, REAL, T0, 2026)
    assert result.accepted
    assert scalar(db, "SELECT count(*) FROM games") == 272
    assert scalar(db, "SELECT count(*) FROM game_changes WHERE change_type = 'created'") == 272
    assert scalar(db, "SELECT count(*) FROM game_source_ids WHERE id_kind = 'espn'") == 272


def test_reingesting_same_snapshot_changes_nothing(db):
    ingest_snapshot(db, REAL, T0, 2026)
    result = ingest_snapshot(db, REAL, T1, 2026)
    assert result.accepted and result.diffs == []
    assert scalar(db, "SELECT count(*) FROM game_changes") == 272
    assert scalar(db, "SELECT max(sequence) FROM games") == 0


def test_moved_game_updates_existing_row_and_keeps_old_source_id(db):
    # MVP proof (DECISIONS.md #5) at the database level: real snapshot, then a
    # HAND-EDITED copy where TB@DAL moves from week 5 Thursday to week 6 Monday.
    ingest_snapshot(db, REAL, T0, 2026)
    gid, uid, *_ = game_by_key(db, "DAL", "TB")

    moved = edit_csv(REAL, "2026_05_TB_DAL", game_id="2026_06_TB_DAL", week="6",
                     gameday="2026-10-19", weekday="Monday")
    result = ingest_snapshot(db, moved, T1, 2026)

    assert result.accepted
    assert scalar(db, "SELECT count(*) FROM games") == 272
    assert game_by_key(db, "DAL", "TB") == (gid, uid, 6, 1, "scheduled")
    fields = {r[0] for r in db.execute(
        "SELECT field FROM game_changes WHERE game_id = %s AND change_type = 'updated'", (gid,))}
    assert fields == {"week", "start_utc"}
    both_ids = {r[0] for r in db.execute(
        "SELECT external_id FROM game_source_ids WHERE game_id = %s AND id_kind = 'game_id'", (gid,))}
    assert both_ids == {"2026_05_TB_DAL", "2026_06_TB_DAL"}


def test_dropped_game_cancelled_then_restored(db):
    ingest_snapshot(db, REAL, T0, 2026)
    gid, uid, *_ = game_by_key(db, "DAL", "TB")

    ingest_snapshot(db, edit_csv(REAL, "2026_05_TB_DAL", drop=True), T1, 2026)
    assert game_by_key(db, "DAL", "TB")[3:] == (1, "cancelled")

    ingest_snapshot(db, REAL, T1, 2026)
    assert game_by_key(db, "DAL", "TB") == (gid, uid, 5, 2, "scheduled")
    types = [r[0] for r in db.execute(
        "SELECT change_type FROM game_changes WHERE game_id = %s ORDER BY id", (gid,))]
    assert types == ["created", "cancelled", "restored"]


def test_truncated_snapshot_rejected_and_nothing_changes(db):
    ingest_snapshot(db, REAL, T0, 2026)
    half = "\n".join(REAL.splitlines()[:137]) + "\n"
    result = ingest_snapshot(db, half, T1, 2026)

    assert not result.accepted
    assert "row count dropped" in result.reject_reason
    assert scalar(db, "SELECT count(*) FROM games WHERE status = 'cancelled'") == 0
    assert scalar(db, "SELECT reject_reason FROM snapshots WHERE NOT accepted") == result.reject_reason


def test_malformed_file_rejected(db):
    result = ingest_snapshot(db, "<html>rate limited</html>", T0, 2026)
    assert not result.accepted
    assert result.reject_reason.startswith("parse error")
    assert scalar(db, "SELECT count(*) FROM games") == 0


def test_unknown_team_rejected(db):
    bad = edit_csv(REAL, "2026_05_TB_DAL", home_team="XXX")
    result = ingest_snapshot(db, bad, T0, 2026)
    assert result.reject_reason == "unknown teams: XXX"


def test_failure_midway_rolls_back_everything(db, monkeypatch):
    def boom(*_):
        raise RuntimeError("simulated crash after games were written")
    monkeypatch.setattr(store, "_upsert_source_ids", boom)

    with pytest.raises(RuntimeError):
        ingest_snapshot(db, REAL, T0, 2026)
    assert scalar(db, "SELECT count(*) FROM games") == 0
    assert scalar(db, "SELECT count(*) FROM snapshots") == 0


def test_games_loaded_from_db_replan_to_no_changes(db):
    # Guards the timezone/hash round trip through Postgres.
    db.execute("SET TIME ZONE 'America/Los_Angeles'")
    ingest_snapshot(db, REAL, T0, 2026)
    assert all(g.start_utc.utcoffset().total_seconds() != 0 for g in load_games(db, 2026))
    assert ingest_snapshot(db, REAL, T1, 2026).diffs == []


def test_raw_snapshot_saved_with_hash_in_name(tmp_path):
    path = save_raw_snapshot("a,b\n", T0, tmp_path)
    assert path.read_text() == "a,b\n"
    assert path.name.startswith("nflverse_20261003T200000Z_")
