"""Fetch the current nflverse schedule and ingest it.

Usage:
    uv run python -m fixturefeed.ingest            # download from nflverse
    uv run python -m fixturefeed.ingest FILE.csv   # ingest a local file
"""

import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fixturefeed import config
from fixturefeed.db import connect
from fixturefeed.store import ingest_snapshot, save_raw_snapshot


def fetch_nflverse(url: str = config.NFLVERSE_GAMES_URL) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main(argv: list[str]) -> int:
    fetched_at = datetime.now(timezone.utc)
    raw = Path(argv[0]).read_text() if argv else fetch_nflverse()
    path = save_raw_snapshot(raw, fetched_at, Path(config.SNAPSHOT_DIR))

    with connect() as conn:
        result = ingest_snapshot(conn, raw, fetched_at, config.CURRENT_SEASON)

    if not result.accepted:
        print(f"snapshot {result.snapshot_id} REJECTED: {result.reject_reason} (raw: {path})")
        return 1
    counts: dict[str, int] = {}
    for d in result.diffs:
        counts[d.change_type] = counts.get(d.change_type, 0) + 1
    summary = ", ".join(f"{n} {t}" for t, n in sorted(counts.items())) or "no changes"
    print(f"snapshot {result.snapshot_id} accepted: {summary} (raw: {path})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
