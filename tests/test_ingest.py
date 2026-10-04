from contextlib import contextmanager

from fixturefeed.ingest import Fetched, run_forever, run_once
from tests.test_store import REAL, edit_csv


class FakeSource:
    """Stands in for nflverse: serves queued responses and records ETags sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent_etags = []

    def __call__(self, etag):
        self.sent_etags.append(etag)
        return self.responses.pop(0)


def run(db, source, tmp_path):
    @contextmanager
    def connect_db():
        yield db
    return run_once(fetch=source, snapshot_dir=tmp_path, connect_db=connect_db)


def test_first_run_ingests_and_stores_etag(db, tmp_path):
    source = FakeSource(Fetched(REAL, '"v1"'))
    assert "272 created" in run(db, source, tmp_path)
    assert source.sent_etags == [None]
    assert db.execute("SELECT http_etag FROM snapshots").fetchone() == ('"v1"',)
    assert len(list(tmp_path.iterdir())) == 1


def test_not_modified_skips_everything(db, tmp_path):
    source = FakeSource(Fetched(REAL, '"v1"'), Fetched(None, '"v1"'))
    run(db, source, tmp_path)
    assert run(db, source, tmp_path) == "unchanged (HTTP 304)"
    assert source.sent_etags == [None, '"v1"']
    assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_identical_content_with_new_etag_skips_everything(db, tmp_path):
    source = FakeSource(Fetched(REAL, '"v1"'), Fetched(REAL, '"v2"'))
    run(db, source, tmp_path)
    assert run(db, source, tmp_path) == "unchanged (same content)"
    assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 1


def test_changed_content_is_ingested(db, tmp_path):
    moved = edit_csv(REAL, "2026_05_TB_DAL", gameday="2026-10-09", weekday="Friday")
    source = FakeSource(Fetched(REAL, '"v1"'), Fetched(moved, '"v2"'))
    run(db, source, tmp_path)
    assert "1 updated" in run(db, source, tmp_path)


def test_loop_survives_a_failed_cycle():
    calls, sleeps = [], []

    def cycle():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("network down")
        return "ok"

    run_forever(30, cycle=cycle, sleep=sleeps.append, max_cycles=3)
    assert len(calls) == 3
    assert sleeps == [1800, 1800]
