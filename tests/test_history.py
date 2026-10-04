from xml.etree import ElementTree as ET

from fixturefeed.history import load_team_history
from fixturefeed.store import ingest_snapshot
from tests.test_store import REAL, T0, T1, edit_csv

ATOM = "{http://www.w3.org/2005/Atom}"
MOVED = edit_csv(REAL, "2026_05_TB_DAL", game_id="2026_06_TB_DAL", week="6",
                 gameday="2026-10-19", weekday="Monday")  # HAND-EDITED move


def test_initial_load_is_not_history(db):
    ingest_snapshot(db, REAL, T0, 2026)
    assert load_team_history(db, "DAL", 2026) == []


def test_move_described_in_plain_english(db):
    ingest_snapshot(db, REAL, T0, 2026)
    ingest_snapshot(db, MOVED, T1, 2026)
    [entry] = load_team_history(db, "DAL", 2026)
    assert entry.title == "Tampa Bay Buccaneers at Dallas Cowboys"
    assert entry.messages == [
        "Kickoff moved from Thu Oct 8, 8:15 PM ET to Mon Oct 19, 8:15 PM ET.",
        "Now listed in week 6 (was week 5).",
    ]
    assert entry.kickoff_now == "Mon Oct 19, 8:15 PM ET"
    assert load_team_history(db, "TB", 2026)[0].entry_id == entry.entry_id
    assert load_team_history(db, "SF", 2026) == []


def test_tbd_announcement_and_cancellation_described(db):
    ingest_snapshot(db, REAL, T0, 2026)
    announced = edit_csv(REAL, "2026_18_SF_ARI", gametime="16:25")
    ingest_snapshot(db, announced, T1, 2026)
    [entry] = load_team_history(db, "SF", 2026)
    assert entry.messages == ["Kickoff time announced: Sun Jan 10, 4:25 PM ET."]

    ingest_snapshot(db, edit_csv(announced, "2026_18_SF_ARI", drop=True), T1, 2026)
    newest = load_team_history(db, "SF", 2026)[0]
    assert newest.messages == ["No longer on the schedule. Marked cancelled."]


def test_history_page(client, db):
    ingest_snapshot(db, MOVED, T1, 2026)
    page = client.get("/teams/DAL/changes")
    assert page.status_code == 200
    assert "Kickoff moved from Thu Oct 8, 8:15 PM ET to Mon Oct 19, 8:15 PM ET." in page.text
    assert "No schedule changes detected yet" in client.get("/teams/SF/changes").text
    assert client.get("/teams/XXX/changes").status_code == 404


def test_atom_feed_is_valid_and_stable(client, db):
    ingest_snapshot(db, MOVED, T1, 2026)
    resp = client.get("/teams/DAL/changes.atom")
    assert resp.headers["content-type"] == "application/atom+xml; charset=utf-8"
    root = ET.fromstring(resp.content)
    assert root.tag == f"{ATOM}feed"
    [entry] = root.findall(f"{ATOM}entry")
    assert entry.find(f"{ATOM}title").text.startswith("Tampa Bay Buccaneers at Dallas Cowboys: Kickoff moved")
    # Same entry ID on every fetch, so readers don't re-notify.
    again = ET.fromstring(client.get("/teams/DAL/changes.atom").content)
    assert again.find(f"{ATOM}entry/{ATOM}id").text == entry.find(f"{ATOM}id").text


def test_feed_page_links_to_history(client):
    resp = client.post("/feeds", data={"team": "DAL"}, follow_redirects=False)
    page = client.get(resp.headers["location"]).text
    assert 'href="/teams/DAL/changes"' in page
