from datetime import datetime, timezone
from pathlib import Path

import pytest

from fixturefeed.sources.nflverse import SnapshotError, parse_games

FIXTURES = Path(__file__).parent / "fixtures"
# Real nflverse snapshot, 2026 rows only, downloaded 2026-10-03.
SNAPSHOT = (FIXTURES / "nflverse_2026_snapshot_2026-10-03.csv").read_text()

HEADER = "game_id,season,game_type,week,gameday,weekday,gametime,away_team,home_team,stadium,espn\n"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def games():
    return {g.source_ids["game_id"]: g for g in parse_games(SNAPSHOT, 2026)}


# --- Real snapshot -------------------------------------------------------

def test_full_2026_season_parsed(games):
    assert len(games) == 272


def test_natural_keys_unique_in_real_snapshot(games):
    keys = [g.natural_key for g in games.values()]
    assert len(keys) == len(set(keys))


def test_eastern_daylight_time_converted_to_utc(games):
    # Thu 2026-10-01 20:15 EDT (UTC-4) -> next day 00:15 UTC
    assert games["2026_04_PIT_CLE"].start_utc == utc(2026, 10, 2, 0, 15)


def test_eastern_standard_time_after_dst_ends(games):
    # DST ends 2026-11-01; Sun 2026-11-08 13:00 EST (UTC-5) -> 18:00 UTC
    assert games["2026_09_DEN_CAR"].start_utc == utc(2026, 11, 8, 18, 0)


def test_london_game_listed_in_eastern(games):
    # 09:30 ET listing for a London kickoff -> 13:30 UTC
    assert games["2026_04_IND_WAS"].start_utc == utc(2026, 10, 4, 13, 30)


def test_week_18_placeholder_times_marked_tbd(games):
    week18 = [g for g in games.values() if g.week == 18]
    assert week18 and all(g.time_tbd for g in week18)


def test_announced_weeks_not_tbd(games):
    assert not any(g.time_tbd for g in games.values() if g.week < 18)


def test_source_ids_kept_and_old_game_id_dropped(games):
    ids = games["2026_04_PIT_CLE"].source_ids
    assert ids == {"game_id": "2026_04_PIT_CLE", "espn": "401872964",
                   "gsis": "60226", "pfr": "202610010cle"}


def test_future_game_without_gsis_has_no_gsis_key(games):
    assert "gsis" not in games["2026_09_DEN_CAR"].source_ids


def test_other_seasons_excluded():
    assert parse_games(SNAPSHOT, 2025) == []


# --- TBD rule edge cases (synthetic) -------------------------------------

def test_single_sunday_game_is_not_tbd():
    # e.g. a Christmas week where only the night game is on Sunday
    csv_text = HEADER + "2026_16_CHI_GB,2026,REG,16,2026-12-27,Sunday,20:20,CHI,GB,Lambeau,1\n"
    [g] = parse_games(csv_text, 2026)
    assert not g.time_tbd


def test_thursday_game_in_tbd_week_keeps_real_time():
    csv_text = HEADER + (
        "a,2026,REG,18,2027-01-07,Thursday,20:15,A1,H1,S,1\n"
        "b,2026,REG,18,2027-01-10,Sunday,13:00,A2,H2,S,2\n"
        "c,2026,REG,18,2027-01-10,Sunday,13:00,A3,H3,S,3\n"
    )
    by_id = {g.source_ids["game_id"]: g for g in parse_games(csv_text, 2026)}
    assert not by_id["a"].time_tbd
    assert by_id["b"].time_tbd and by_id["c"].time_tbd


def test_blank_gametime_is_tbd():
    csv_text = HEADER + "x,2026,WC,19,2027-01-16,Saturday,,A,H,S,9\n"
    [g] = parse_games(csv_text, 2026)
    assert g.time_tbd


# --- Malformed input ------------------------------------------------------

def test_missing_column_rejected():
    with pytest.raises(SnapshotError, match="missing columns"):
        parse_games("game_id,season\nx,2026\n", 2026)


def test_bad_date_rejected():
    csv_text = HEADER + "x,2026,REG,1,not-a-date,Sunday,13:00,A,H,S,1\n"
    with pytest.raises(SnapshotError, match="bad row 'x'"):
        parse_games(csv_text, 2026)
