"""Human-readable schedule change history (DECISIONS.md #8: change-history page).

Turns `game_changes` rows into one entry per game per snapshot, e.g.
"Kickoff moved from Thu Oct 8, 8:15 PM ET to Mon Oct 19, 8:15 PM ET".
Used by the history page and the Atom change feed.
"""

from dataclasses import dataclass, field
from datetime import datetime

import psycopg

from fixturefeed.feed import format_et
from fixturefeed.sources import nflverse


@dataclass
class HistoryEntry:
    game_id: str
    snapshot_id: int
    detected_at: datetime
    title: str  # "Tampa Bay Buccaneers at Dallas Cowboys"
    kickoff_now: str  # current kickoff, formatted
    messages: list[str] = field(default_factory=list)

    @property
    def entry_id(self) -> str:
        return f"{self.snapshot_id}-{self.game_id}"


def first_snapshot(conn: psycopg.Connection) -> tuple[int, datetime] | None:
    """The first accepted snapshot: everything 'created' there is the initial load."""
    return conn.execute(
        """SELECT id, fetched_at FROM snapshots
           WHERE source = %s AND accepted ORDER BY id LIMIT 1""",
        (nflverse.SOURCE,),
    ).fetchone()


def load_team_history(
    conn: psycopg.Connection, team: str, season: int, limit: int = 200
) -> list[HistoryEntry]:
    first = first_snapshot(conn)
    if first is None:
        return []
    rows = conn.execute(
        """SELECT c.game_id, c.snapshot_id, s.fetched_at, c.change_type, c.field,
                  c.old_value, c.new_value, a.name, h.name, g.start_utc, g.time_tbd,
                  g.status
           FROM game_changes c
           JOIN snapshots s ON s.id = c.snapshot_id
           JOIN games g ON g.id = c.game_id
           JOIN teams h ON h.abbr = g.home_team
           JOIN teams a ON a.abbr = g.away_team
           WHERE g.season = %s AND %s IN (g.home_team, g.away_team)
             AND NOT (c.change_type = 'created' AND c.snapshot_id = %s)
           ORDER BY c.snapshot_id DESC, c.game_id, c.id""",
        (season, team, first[0]),
    ).fetchall()

    entries: dict[tuple, HistoryEntry] = {}
    changes: dict[tuple, dict] = {}
    for (game_id, snap_id, fetched_at, ctype, fld, old, new,
         away, home, start, tbd, status) in rows:
        key = (snap_id, game_id)
        if key not in entries:
            kickoff = format_et(start, with_time=not tbd) + (" (time TBD)" if tbd else "")
            entries[key] = HistoryEntry(str(game_id), snap_id, fetched_at,
                                        f"{away} at {home}", kickoff)
            changes[key] = {"types": [], "fields": {}}
        if fld is None:
            changes[key]["types"].append(ctype)
        else:
            changes[key]["fields"][fld] = (old, new)

    for key, entry in entries.items():
        entry.messages = _describe(changes[key]["types"], changes[key]["fields"])
    return list(entries.values())[:limit]


def _describe(types: list[str], fields: dict[str, tuple]) -> list[str]:
    msgs = []
    if "created" in types:
        msgs.append("Added to the schedule.")
    if "cancelled" in types:
        msgs.append("No longer on the schedule. Marked cancelled.")
    if "restored" in types:
        msgs.append("Back on the schedule.")

    tbd = fields.get("time_tbd")
    start = fields.get("start_utc")
    if tbd and tbd[1] == "false":
        when = f": {_fmt(start[1])}" if start else ""
        msgs.append(f"Kickoff time announced{when}.")
    elif tbd and tbd[1] == "true":
        msgs.append("Kickoff time is now TBD.")
    elif start:
        msgs.append(f"Kickoff moved from {_fmt(start[0])} to {_fmt(start[1])}.")

    if "home_team" in fields or "away_team" in fields:
        msgs.append("Home and away teams changed.")
    if venue := fields.get("venue"):
        msgs.append(f"Venue changed from {venue[0] or 'unknown'} to {venue[1] or 'unknown'}.")
    if week := fields.get("week"):
        msgs.append(f"Now listed in week {week[1]} (was week {week[0]}).")
    return msgs or ["Schedule details updated."]


def _fmt(iso: str) -> str:
    return format_et(datetime.fromisoformat(iso))
