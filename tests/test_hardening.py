from fixturefeed.ratelimit import LINKS_PER_WINDOW, allow_link_event, ip_hash


def new_link(client, team="SF"):
    return client.post("/feeds", data={"team": team}, follow_redirects=False)


def token_of(resp):
    return resp.headers["location"].split("/feeds/")[1].split("?")[0]


def test_limiter_counts_per_ip_and_window(db):
    for _ in range(LINKS_PER_WINDOW):
        assert allow_link_event(db, "1.2.3.4")
    assert not allow_link_event(db, "1.2.3.4")
    assert allow_link_event(db, "5.6.7.8")  # other clients unaffected
    db.execute("UPDATE link_events SET at = now() - interval '61 minutes'")
    assert allow_link_event(db, "1.2.3.4")  # window slid


def test_limiter_stores_only_hashed_ips(db):
    allow_link_event(db, "1.2.3.4")
    [(stored,)] = db.execute("SELECT ip_hash FROM link_events").fetchall()
    assert stored == ip_hash("1.2.3.4") and "1.2.3.4" not in stored


def test_link_creation_rate_limited(client):
    for _ in range(LINKS_PER_WINDOW):
        assert new_link(client).status_code == 303
    assert new_link(client).status_code == 429


def test_forwarded_client_ip_is_used(client, db):
    client.post("/feeds", data={"team": "SF"}, headers={"x-real-ip": "9.9.9.9"},
                follow_redirects=False)
    assert db.execute("SELECT ip_hash FROM link_events").fetchone()[0] == ip_hash("9.9.9.9")


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
