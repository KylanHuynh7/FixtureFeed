import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fixturefeed.diff import (
    MatchConflict, content_hash, plan_changes, validate_snapshot,
)
from fixturefeed.models import SourceGame
from fixturefeed.sources.nflverse import parse_games

FIXTURES = Path(__file__).parent / "fixtures"


def src(home="CLE", away="PIT", week=4, start=(2026, 10, 2, 0, 15), tbd=False,
        espn="1", game_id=None, venue="Huntington Bank Field", game_type="REG"):
    ids = {"game_id": game_id or f"2026_{week:02d}_{away}_{home}"}
    if espn:
        ids["espn"] = espn
    return SourceGame(
        season=2026, game_type=game_type, week=week, home_team=home, away_team=away,
        start_utc=datetime(*start, tzinfo=timezone.utc), time_tbd=tbd, venue=venue,
        source_ids=ids,
    )


class Store:
    """In-memory stand-in for the database: applies plans like persistence will."""

    def __init__(self):
        self.games = {}
        self.espn = {}

    def sync(self, incoming):
        plan = plan_changes(list(self.games.values()), incoming, dict(self.espn))
        for d in plan.diffs:
            self.games[d.game.id] = d.game
        for gid, kind, ext in plan.source_ids:
            if kind == "espn":
                self.espn[ext] = gid
        return plan

    def only(self):
        [g] = self.games.values()
        return g


# --- Creation and no-op --------------------------------------------------

def test_first_snapshot_creates_games_with_stable_uid():
    store = Store()
    plan = store.sync([src()])
    [d] = plan.diffs
    assert d.change_type == "created"
    assert d.game.sequence == 0
    assert d.game.ics_uid == f"{d.game.id}@fixturefeed"


def test_identical_snapshot_produces_no_changes():
    store = Store()
    store.sync([src()])
    assert store.sync([src()]).diffs == []


# --- Updates keep identity -----------------------------------------------

def test_kickoff_change_updates_same_event_and_bumps_sequence():
    store = Store()
    store.sync([src()])
    before = store.only()

    plan = store.sync([src(start=(2026, 10, 2, 1, 15))])
    [d] = plan.diffs
    assert d.change_type == "updated"
    assert d.game.ics_uid == before.ics_uid
    assert d.game.sequence == 1
    assert [c.field for c in d.field_changes] == ["start_utc"]


def test_game_moved_to_another_week_keeps_uid_despite_new_nflverse_id():
    # The real 2020 DEN@NE case: game_id changed from week 5 to week 6.
    store = Store()
    store.sync([src(home="NE", away="DEN", week=5, start=(2026, 10, 11, 17, 0))])
    uid = store.only().ics_uid

    plan = store.sync([src(home="NE", away="DEN", week=6, start=(2026, 10, 18, 17, 0))])
    [d] = plan.diffs
    assert d.game.ics_uid == uid
    assert {c.field for c in d.field_changes} == {"week", "start_utc"}
    assert d.game.sequence == 1
    assert len(store.games) == 1


def test_invisible_change_is_logged_without_sequence_bump():
    store = Store()
    store.sync([src(week=4)])
    [d] = store.sync([src(week=5)]).diffs  # same kickoff, different week label
    assert [c.field for c in d.field_changes] == ["week"]
    assert d.game.sequence == 0


def test_tbd_time_announced_bumps_sequence():
    store = Store()
    store.sync([src(week=18, tbd=True, start=(2027, 1, 10, 18, 0))])
    [d] = store.sync([src(week=18, tbd=False, start=(2027, 1, 10, 21, 25))]).diffs
    assert {c.field for c in d.field_changes} == {"start_utc", "time_tbd"}
    assert d.game.sequence == 1


def test_home_away_swap_matched_by_espn_id():
    store = Store()
    store.sync([src(home="CLE", away="PIT", espn="777")])
    uid = store.only().ics_uid
    [d] = store.sync([src(home="PIT", away="CLE", espn="777")]).diffs
    assert d.game.ics_uid == uid
    assert d.game.sequence == 1


def test_same_instant_in_other_timezone_is_not_a_change():
    store = Store()
    store.sync([src()])
    g = store.only()
    pacific = g.start_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    reloaded = replace(g, start_utc=pacific)  # how Postgres may hand it back
    assert content_hash(reloaded) == g.content_hash
    assert plan_changes([reloaded], [src()], {"1": g.id}).diffs == []


# --- Cancellation and restoration ----------------------------------------

def test_missing_game_is_cancelled_once():
    store = Store()
    store.sync([src(), src(home="BUF", away="NE", espn="2")])
    [d] = store.sync([src(home="BUF", away="NE", espn="2")]).diffs
    assert d.change_type == "cancelled"
    assert d.game.status == "cancelled"
    assert d.game.sequence == 1
    # Still missing next time: nothing new to say.
    assert store.sync([src(home="BUF", away="NE", espn="2")]).diffs == []


def test_cancelled_game_that_returns_is_restored_with_same_uid():
    store = Store()
    other = src(home="BUF", away="NE", espn="2")
    store.sync([src(), other])
    uid = next(g.ics_uid for g in store.games.values() if g.home_team == "CLE")
    store.sync([other])

    plan = store.sync([src(start=(2026, 10, 3, 17, 0)), other])
    [d] = plan.diffs
    assert d.change_type == "restored"
    assert d.game.ics_uid == uid
    assert d.game.status == "scheduled"
    assert d.game.sequence == 2
    assert [c.field for c in d.field_changes] == ["start_utc"]


# --- Conflicts -----------------------------------------------------------

def test_keys_pointing_at_different_games_raise_conflict():
    store = Store()
    store.sync([src(home="CLE", away="PIT", espn="1"), src(home="BUF", away="NE", espn="2")])
    with pytest.raises(MatchConflict):
        store.sync([src(home="CLE", away="PIT", espn="2")])


def test_two_rows_matching_one_game_raise_conflict():
    store = Store()
    store.sync([src(home="CLE", away="PIT", espn="1")])
    with pytest.raises(MatchConflict):
        store.sync([src(home="CLE", away="PIT", espn="9"),
                    src(home="PIT", away="CLE", espn="1")])


# --- Snapshot validation -------------------------------------------------

def _stored(store):
    return list(store.games.values())


def test_valid_snapshot_passes():
    assert validate_snapshot([src()], [], None) is None


def test_empty_snapshot_rejected():
    assert "no games" in validate_snapshot([], [], 272)


def test_duplicate_games_rejected():
    assert "duplicate games" in validate_snapshot([src(espn="1"), src(espn="2")], [], None)


def test_duplicate_espn_ids_rejected():
    reason = validate_snapshot([src(espn="1"), src(home="BUF", away="NE", espn="1")], [], None)
    assert "ESPN" in reason


def test_row_count_drop_over_5_percent_rejected():
    games = [src(home="CLE", away=f"T{i}", espn=str(i)) for i in range(94)]
    assert "dropped from 100 to 94" in validate_snapshot(games, [], 100)


def test_row_count_drop_within_5_percent_allowed():
    games = [src(home="CLE", away=f"T{i}", espn=str(i)) for i in range(95)]
    assert validate_snapshot(games, [], 100) is None


def test_team_disappearing_rejected():
    store = Store()
    store.sync([src(), src(home="BUF", away="NE", espn="2")])
    reason = validate_snapshot([src()], _stored(store), None)
    assert reason == "teams with no games: BUF, NE"


# --- Real snapshot (recorded 2026-10-03) ---------------------------------

@pytest.fixture(scope="module")
def real_games():
    text = (FIXTURES / "nflverse_2026_snapshot_2026-10-03.csv").read_text()
    return parse_games(text, 2026)


def test_real_snapshot_creates_272_then_replays_cleanly(real_games):
    store = Store()
    assert validate_snapshot(real_games, [], None) is None
    plan = store.sync(real_games)
    assert len(plan.diffs) == 272
    assert {d.change_type for d in plan.diffs} == {"created"}
    assert store.sync(real_games).diffs == []


def test_real_game_moved_a_week_updates_in_place(real_games):
    # HAND-EDITED from the real snapshot: simulate TB@DAL (week 5, Thu) being
    # postponed to the following Monday in week 6, as nflverse would publish it.
    store = Store()
    store.sync(real_games)
    target = next(g for g in real_games if g.source_ids["game_id"] == "2026_05_TB_DAL")
    uid = next(g.ics_uid for g in store.games.values() if g.natural_key == target.natural_key)

    moved = replace(target, week=6,
                    start_utc=datetime(2026, 10, 20, 0, 15, tzinfo=timezone.utc),
                    source_ids=target.source_ids | {"game_id": "2026_06_TB_DAL"})
    edited = [moved if g is target else g for g in real_games]

    plan = store.sync(edited)
    [d] = plan.diffs
    assert d.change_type == "updated"
    assert d.game.ics_uid == uid
    assert d.game.sequence == 1
    assert len(store.games) == 272
