"""Round-trip tests: generate ICS with `icalendar`, parse it back with the
independent `vobject` parser (DECISIONS.md #6, #15)."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import vobject

from fixturefeed.feed import load_team_games, render_team_feed
from fixturefeed.store import ingest_snapshot
from tests.test_store import REAL, T0, T1, edit_csv


def feed_for(db, team, name):
    return render_team_feed(name, load_team_games(db, team, 2026))


def parse(ics: bytes):
    cal = vobject.readOne(ics.decode())
    return {ev.uid.value: ev for ev in cal.vevent_list}


@pytest.fixture
def ingested(db):
    ingest_snapshot(db, REAL, T0, 2026)
    return db


def test_team_feed_has_every_game_once(ingested):
    events = parse(feed_for(ingested, "SF", "San Francisco 49ers"))
    db_uids = {r[0] for r in ingested.execute(
        "SELECT ics_uid FROM games WHERE 'SF' IN (home_team, away_team)")}
    assert set(events) == db_uids
    assert len(events) == 17


def test_timed_event_parses_to_correct_instant(ingested):
    raw = feed_for(ingested, "CLE", "Cleveland Browns")
    assert b"DTSTART;TZID=America/New_York:20261001T201500" in raw
    events = parse(raw)
    ev = next(e for e in events.values() if e.summary.value == "Pittsburgh Steelers at Cleveland Browns")
    assert ev.dtstart.value == datetime(2026, 10, 2, 0, 15, tzinfo=timezone.utc)
    assert ev.description.value.startswith("Kickoff: Thu Oct 1, 8:15 PM ET")
    assert ev.status.value == "CONFIRMED"
    assert int(ev.sequence.value) == 0


def test_standard_time_game_after_dst_ends_parses_correctly(ingested):
    # Sun Nov 8 2026 1:00 PM EST (UTC-5). Guards the VTIMEZONE rules.
    events = parse(feed_for(ingested, "CAR", "Carolina Panthers"))
    ev = next(e for e in events.values() if e.summary.value == "Denver Broncos at Carolina Panthers")
    assert ev.dtstart.value == datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)
    assert ev.description.value.startswith("Kickoff: Sun Nov 8, 1:00 PM ET")


def test_tbd_game_is_all_day_and_tentative(ingested):
    events = parse(feed_for(ingested, "SF", "San Francisco 49ers"))
    ev = next(e for e in events.values() if "(time TBD)" in e.summary.value)
    assert ev.dtstart.value == date(2027, 1, 10)
    assert ev.dtend.value == date(2027, 1, 11)
    assert ev.status.value == "TENTATIVE"


def test_moved_game_keeps_uid_and_bumps_sequence_in_feed(ingested):
    # MVP proof (DECISIONS.md #5) at the feed level, using a HAND-EDITED move
    # of the real TB@DAL game from Thu Oct 8 to Mon Oct 19.
    before = parse(feed_for(ingested, "DAL", "Dallas Cowboys"))
    moved = edit_csv(REAL, "2026_05_TB_DAL", game_id="2026_06_TB_DAL", week="6",
                     gameday="2026-10-19", weekday="Monday")
    ingest_snapshot(ingested, moved, T1, 2026)
    after = parse(feed_for(ingested, "DAL", "Dallas Cowboys"))

    assert set(after) == set(before)  # same events, no duplicate
    [uid] = [u for u in after if int(after[u].sequence.value) == 1]
    assert before[uid].summary.value == "Tampa Bay Buccaneers at Dallas Cowboys"
    assert before[uid].dtstart.value == datetime(2026, 10, 9, 0, 15, tzinfo=timezone.utc)
    assert after[uid].dtstart.value == datetime(2026, 10, 20, 0, 15, tzinfo=timezone.utc)


def test_cancelled_game_marked_in_feed(ingested):
    ingest_snapshot(ingested, edit_csv(REAL, "2026_05_TB_DAL", drop=True), T1, 2026)
    events = parse(feed_for(ingested, "DAL", "Dallas Cowboys"))
    ev = next(e for e in events.values() if "Tampa Bay" in e.summary.value)
    assert ev.summary.value.startswith("CANCELLED: ")
    assert ev.status.value == "CANCELLED"
    assert int(ev.sequence.value) == 1
    assert len(events) == 17


def test_feed_is_deterministic(ingested):
    assert feed_for(ingested, "SF", "x") == feed_for(ingested, "SF", "x")


def test_feed_follows_rfc5545_line_rules(ingested):
    raw = feed_for(ingested, "SF", "San Francisco 49ers")
    lines = raw.split(b"\r\n")
    assert raw.endswith(b"\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert max(len(line) for line in lines) <= 75
