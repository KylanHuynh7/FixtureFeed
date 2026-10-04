"""Fetch the current nflverse schedule and ingest it.

Usage:
    uv run python -m fixturefeed.ingest                 # one download + ingest
    uv run python -m fixturefeed.ingest FILE.csv        # ingest a local file
    uv run python -m fixturefeed.ingest --every 30      # repeat every 30 minutes

Downloads are conditional (If-None-Match), and a download identical to the
previous snapshot is skipped entirely, so frequent runs cost almost nothing.
"""

import argparse
import hashlib
import logging
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fixturefeed import config
from fixturefeed.db import connect
from fixturefeed.store import ingest_snapshot, last_snapshot, save_raw_snapshot

log = logging.getLogger("fixturefeed.ingest")
USER_AGENT = f"{config.APP_NAME}/0.1 (non-commercial student project)"


@dataclass(frozen=True)
class Fetched:
    raw: str | None  # None means "not modified since the given ETag"
    etag: str | None


def fetch_nflverse(etag: str | None = None, url: str = config.NFLVERSE_GAMES_URL) -> Fetched:
    headers = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
            return Fetched(resp.read().decode("utf-8"), resp.headers.get("ETag"))
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return Fetched(None, etag)
        raise


def run_once(
    fetch: Callable[[str | None], Fetched] = fetch_nflverse,
    snapshot_dir: Path = Path(config.SNAPSHOT_DIR),
    connect_db=connect,
) -> str:
    """One fetch-and-ingest cycle. Returns a one-line summary."""
    with connect_db() as conn:
        previous = last_snapshot(conn)
        fetched = fetch(previous[1] if previous else None)
        if fetched.raw is None:
            return "unchanged (HTTP 304)"
        if previous and hashlib.sha256(fetched.raw.encode()).hexdigest() == previous[0]:
            return "unchanged (same content)"

        fetched_at = datetime.now(timezone.utc)
        path = save_raw_snapshot(fetched.raw, fetched_at, snapshot_dir)
        result = ingest_snapshot(conn, fetched.raw, fetched_at, config.CURRENT_SEASON, fetched.etag)

    if not result.accepted:
        return f"snapshot {result.snapshot_id} REJECTED: {result.reject_reason} (raw: {path})"
    return f"snapshot {result.snapshot_id} accepted: {_summarize(result.diffs)} (raw: {path})"


def run_forever(
    every_minutes: float,
    cycle: Callable[[], str] = run_once,
    sleep: Callable[[float], None] = time.sleep,
    max_cycles: int | None = None,
) -> None:
    """Run `cycle` on a fixed interval. A failed cycle is logged, never fatal."""
    n = 0
    while max_cycles is None or n < max_cycles:
        try:
            log.info(cycle())
        except Exception:
            log.exception("ingest cycle failed; will retry next interval")
        n += 1
        if max_cycles is None or n < max_cycles:
            sleep(every_minutes * 60)


def ingest_file(path: Path) -> str:
    raw = path.read_text()
    fetched_at = datetime.now(timezone.utc)
    saved = save_raw_snapshot(raw, fetched_at, Path(config.SNAPSHOT_DIR))
    with connect() as conn:
        result = ingest_snapshot(conn, raw, fetched_at, config.CURRENT_SEASON)
    if not result.accepted:
        return f"snapshot {result.snapshot_id} REJECTED: {result.reject_reason} (raw: {saved})"
    return f"snapshot {result.snapshot_id} accepted: {_summarize(result.diffs)} (raw: {saved})"


def _summarize(diffs) -> str:
    counts: dict[str, int] = {}
    for d in diffs:
        counts[d.change_type] = counts.get(d.change_type, 0) + 1
    return ", ".join(f"{n} {t}" for t, n in sorted(counts.items())) or "no changes"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m fixturefeed.ingest")
    parser.add_argument("file", nargs="?", type=Path, help="ingest a local CSV instead of downloading")
    parser.add_argument("--every", type=float, metavar="MINUTES", help="repeat on this interval")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.file:
        summary = ingest_file(args.file)
        print(summary)
        return 1 if "REJECTED" in summary else 0
    if args.every:
        run_forever(args.every)
        return 0
    summary = run_once()
    print(summary)
    return 1 if "REJECTED" in summary else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
