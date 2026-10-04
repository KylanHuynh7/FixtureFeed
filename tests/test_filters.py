import csv
import io

import pytest
import vobject

from fixturefeed.feed import FeedFilter, load_team_games, render_team_feed
from fixturefeed.store import ingest_snapshot
from tests.test_store import REAL, T0

ROWS = [r for r in csv.DictReader(io.StringIO(REAL)) if r["season"] == "2026"]


def expected(team, side="all", primetime=False):
    """Count straight from the raw CSV, independent of our code."""
    n = 0
    for r in ROWS:
        if team not in (r["home_team"], r["away_team"]):
            continue
        if side == "home" and r["home_team"] != team:
            continue
        if side == "away" and r["away_team"] != team:
            continue
        # Week 18 times are placeholders (TBD), so they can't be primetime yet.
        if primetime and (r["week"] == "18" or r["gametime"] < "19:00"):
            continue
        n += 1
    return n


@pytest.fixture
def ingested(db):
    ingest_snapshot(db, REAL, T0, 2026)
    return db


@pytest.mark.parametrize("team", ["SF", "DAL", "KC"])
@pytest.mark.parametrize("side", ["all", "home", "away"])
@pytest.mark.parametrize("primetime", [False, True])
def test_filters_match_raw_csv(ingested, team, side, primetime):
    games = load_team_games(ingested, team, 2026, FeedFilter(side, primetime))
    assert len(games) == expected(team, side, primetime)


def test_primetime_excludes_tbd_and_daytime(ingested):
    games = load_team_games(ingested, "SF", 2026, FeedFilter(primetime_only=True))
    assert games and all(not g.time_tbd for g in games)


def test_calendar_title_includes_filter(ingested):
    flt = FeedFilter("home", True)
    cal = vobject.readOne(render_team_feed(
        "San Francisco 49ers", load_team_games(ingested, "SF", 2026, flt), flt).decode())
    assert cal.contents["x-wr-calname"][0].value == "San Francisco 49ers · Home games · Primetime (FixtureFeed)"


def test_web_feed_respects_stored_filters(client):
    resp = client.post("/feeds", data={"team": "SF", "side": "away", "primetime_only": "true"},
                       follow_redirects=False)
    token = resp.headers["location"].rsplit("/", 1)[1]
    assert "Away games · Primetime" in client.get(f"/feeds/{token}").text
    cal = vobject.readOne(client.get(f"/feeds/{token}.ics").text)
    assert len(cal.contents.get("vevent", [])) == expected("SF", "away", True)


def test_unknown_side_rejected(client):
    resp = client.post("/feeds", data={"team": "SF", "side": "neutral"}, follow_redirects=False)
    assert resp.status_code == 400
