import re

import pytest
import vobject
from fastapi.testclient import TestClient

from fixturefeed.store import ingest_snapshot
from fixturefeed.web import app, get_conn
from tests.test_store import REAL, T0


@pytest.fixture
def client(db):
    ingest_snapshot(db, REAL, T0, 2026)
    app.dependency_overrides[get_conn] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_feed(client, team="SF"):
    resp = client.post("/feeds", data={"team": team}, follow_redirects=False)
    assert resp.status_code == 303
    return resp.headers["location"].rsplit("/", 1)[1]


def test_index_lists_all_teams(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert len(re.findall(r"<option value=\"[A-Z]+\">", resp.text)) == 32
    assert "San Francisco 49ers" in resp.text


def test_create_feed_gives_unguessable_token(client, db):
    token = create_feed(client)
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", token)  # 16 bytes, base64url
    assert db.execute("SELECT team_abbr FROM feeds WHERE token = %s", (token,)).fetchone() == ("SF",)
    assert create_feed(client) != token


def test_feed_page_shows_https_and_webcal_links(client):
    token = create_feed(client)
    page = client.get(f"/feeds/{token}").text
    assert f"http://testserver/feeds/{token}.ics" in page
    assert f"webcal://testserver/feeds/{token}.ics" in page


def test_ics_endpoint_serves_parseable_team_calendar(client):
    token = create_feed(client)
    resp = client.get(f"/feeds/{token}.ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/calendar; charset=utf-8"
    cal = vobject.readOne(resp.text)
    assert len(cal.vevent_list) == 17


def test_unchanged_feed_returns_304(client):
    token = create_feed(client)
    first = client.get(f"/feeds/{token}.ics")
    again = client.get(f"/feeds/{token}.ics", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""


def test_unknown_token_is_404(client):
    assert client.get("/feeds/not-a-real-token.ics").status_code == 404
    assert client.get("/feeds/not-a-real-token").status_code == 404


def test_unknown_team_rejected(client, db):
    resp = client.post("/feeds", data={"team": "XXX"}, follow_redirects=False)
    assert resp.status_code == 400
    assert db.execute("SELECT count(*) FROM feeds").fetchone()[0] == 0
