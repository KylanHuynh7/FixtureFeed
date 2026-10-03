"""Adapter for nflverse games.csv (DECISIONS.md #12).

Known source quirks handled here:
- `gametime` is US Eastern clock time with no offset -> converted to UTC.
- TBD kickoffs are not flagged; they appear as a placeholder time shared by
  every Sunday game in the week -> inferred with the rule in `_tbd_weeks`.
- `game_id` embeds the week, so it changes when a game changes weeks; the
  matcher must not rely on it alone.
"""

import csv
import io
from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from fixturefeed.models import SourceGame

SOURCE = "nflverse"
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

REQUIRED_COLUMNS = {
    "game_id", "season", "game_type", "week", "gameday", "weekday",
    "gametime", "away_team", "home_team", "stadium",
}
# Source ID columns we keep. `old_game_id` is skipped: it is date-based and
# not unique (indexes get reassigned when games move).
ID_COLUMNS = ("game_id", "espn", "gsis", "pfr")
# Used only when the source leaves gametime blank; such games are marked TBD.
PLACEHOLDER_KICKOFF = time(13, 0)


class SnapshotError(ValueError):
    """The file can't be trusted as a schedule snapshot."""


def parse_games(csv_text: str, season: int) -> list[SourceGame]:
    """Parse games for one season from the full nflverse games.csv text."""
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
    if missing:
        raise SnapshotError(f"missing columns: {sorted(missing)}")

    rows = [r for r in reader if r["season"] == str(season)]
    tbd_weeks = _tbd_weeks(rows)
    return [_to_source_game(r, tbd_weeks) for r in rows]


def _tbd_weeks(rows: list[dict]) -> set[tuple[str, str]]:
    """Weeks whose kickoff times are placeholders, keyed by (game_type, week).

    Rule (DECISIONS.md #18 C): 2+ Sunday games that all share one kickoff time.
    Real NFL Sundays always mix early, late, and night windows.
    """
    sunday_times: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in rows:
        if r["weekday"] == "Sunday":
            sunday_times[(r["game_type"], r["week"])].append(r["gametime"])
    return {
        week for week, times in sunday_times.items()
        if len(times) >= 2 and len(set(times)) == 1
    }


def _to_source_game(r: dict, tbd_weeks: set[tuple[str, str]]) -> SourceGame:
    try:
        day = datetime.strptime(r["gameday"], "%Y-%m-%d").date()
        kickoff = (
            datetime.strptime(r["gametime"], "%H:%M").time()
            if r["gametime"] else PLACEHOLDER_KICKOFF
        )
        season, week = int(r["season"]), int(r["week"])
    except ValueError as e:
        raise SnapshotError(f"bad row {r.get('game_id')!r}: {e}") from e

    # Only the Sunday games carry the placeholder; Thu/Sat/Mon times in the
    # same week are real announcements.
    time_tbd = not r["gametime"] or (
        r["weekday"] == "Sunday" and (r["game_type"], r["week"]) in tbd_weeks
    )
    start_utc = datetime.combine(day, kickoff, tzinfo=EASTERN).astimezone(UTC)

    return SourceGame(
        season=season,
        game_type=r["game_type"],
        week=week,
        home_team=r["home_team"],
        away_team=r["away_team"],
        start_utc=start_utc,
        time_tbd=time_tbd,
        venue=r["stadium"] or None,
        source_ids={k: r[k] for k in ID_COLUMNS if r.get(k)},
    )
