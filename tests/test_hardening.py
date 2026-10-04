from fixturefeed.ratelimit import SlidingWindowLimiter
from fixturefeed.web import link_limiter


def new_link(client, team="SF"):
    return client.post("/feeds", data={"team": team}, follow_redirects=False)


def token_of(resp):
    return resp.headers["location"].split("/feeds/")[1].split("?")[0]


def test_limiter_window_slides():
    now = [0.0]
    lim = SlidingWindowLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert lim.allow("a") and lim.allow("a")
    assert not lim.allow("a")
    assert lim.allow("b")  # per key
    now[0] = 60.1
    assert lim.allow("a")


def test_link_creation_rate_limited(client):
    for _ in range(link_limiter.limit):
        assert new_link(client).status_code == 303
    assert new_link(client).status_code == 429


def test_replace_link_disables_old_and_keeps_settings(client):
    old = token_of(client.post("/feeds", data={"team": "SF", "side": "home"}, follow_redirects=False))
    resp = client.post(f"/feeds/{old}/replace", follow_redirects=False)
    new = token_of(resp)
    assert new != old
    assert client.get(f"/feeds/{old}.ics").status_code == 404
    page = client.get(f"/feeds/{new}?replaced=1").text
    assert "The old link no longer works" in page and "Home games" in page
    assert client.get(f"/feeds/{new}.ics").status_code == 200


def test_replace_unknown_link_is_404(client):
    assert client.post("/feeds/nope/replace").status_code == 404


def test_privacy_headers_on_every_response(client):
    for path in ["/", "/teams/SF/changes", "/healthz"]:
        resp = client.get(path)
        assert resp.headers["referrer-policy"] == "no-referrer"
        assert resp.headers["x-content-type-options"] == "nosniff"


def test_healthz_reports_stale_ingest(client, db):
    db.execute("UPDATE snapshots SET fetched_at = now() - interval '7 hours'")
    body = client.get("/healthz").json()
    assert body["status"] == "stale"
    assert body["last_accepted"] is not None


def test_healthz_ok_after_recent_fetch(client, db):
    db.execute("UPDATE snapshots SET fetched_at = now()")
    assert client.get("/healthz").json()["status"] == "ok"
