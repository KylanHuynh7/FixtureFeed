"""Render a team's games as an iCalendar (ICS) feed (DECISIONS.md #5, #15, #19).

Output is deterministic for a given database state (DTSTAMP comes from the
game's last change, not the clock), so unchanged feeds are byte-identical.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import psycopg

from fixturefeed.config import APP_NAME

EASTERN = ZoneInfo("America/New_York")
# Assumed length of a game for the calendar block. The source has no end time.
GAME_DURATION = timedelta(hours=3, minutes=30)
# Hint for clients that honor it (Apple, Outlook). Google ignores it.
REFRESH_INTERVAL = timedelta(hours=6)

# Rule-based America/New_York definition (US rules in force since 2007), the
# compact form Google and Apple emit. The generated alternative lists every
# transition 1970-2037 as explicit dates, which at least one parser (vobject)
# misreads; this form is what calendar clients are most tested against.
EASTERN_VTIMEZONE = icalendar.Timezone.from_ical(
    "BEGIN:VTIMEZONE\r\n"
    "TZID:America/New_York\r\n"
    "BEGIN:DAYLIGHT\r\n"
    "TZOFFSETFROM:-0500\r\nTZOFFSETTO:-0400\r\nTZNAME:EDT\r\n"
    "DTSTART:20070311T020000\r\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\r\n"
    "END:DAYLIGHT\r\n"
    "BEGIN:STANDARD\r\n"
    "TZOFFSETFROM:-0400\r\nTZOFFSETTO:-0500\r\nTZNAME:EST\r\n"
    "DTSTART:20071104T020000\r\nRRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\r\n"
    "END:STANDARD\r\n"
    "END:VTIMEZONE\r\n"
)

GAME_TYPE_LABELS = {
    "REG": "Regular season", "WC": "Wild Card round", "DIV": "Divisional round",
    "CON": "Conference championship", "SB": "Super Bowl",
}


# Kickoffs at or after this Eastern time count as primetime (TNF/SNF/MNF and
# Saturday/holiday night games).
PRIMETIME_START_ET = time(19, 0)


@dataclass(frozen=True)
class FeedFilter:
    """Per-feed filters (DECISIONS.md #8). Applied when the feed is rendered."""

    side: str = "all"  # all | home | away
    primetime_only: bool = False

    def matches(self, g: "FeedGame") -> bool:
        if self.side == "home" and not g.is_home:
            return False
        if self.side == "away" and g.is_home:
            return False
        if self.primetime_only:
            # A TBD kickoff can't be classified yet; it joins once announced.
            return not g.time_tbd and g.start_utc.astimezone(EASTERN).time() >= PRIMETIME_START_ET
        return True

    @property
    def label(self) -> str | None:
        parts = {"home": ["Home games"], "away": ["Away games"]}.get(self.side, [])
        if self.primetime_only:
            parts.append("Primetime")
        # " · " not ", ": icalendar writes X-WR-CALNAME commas unescaped, and
        # parsers (vobject, possibly calendar apps) then split the name.
        return " · ".join(parts) or None


@dataclass(frozen=True)
class FeedGame:
    ics_uid: str
    is_home: bool
    game_type: str
    home_name: str
    away_name: str
    start_utc: datetime
    time_tbd: bool
    venue: str | None
    status: str
    sequence: int
    first_seen_at: datetime
    updated_at: datetime


def load_team_games(
    conn: psycopg.Connection, team: str, season: int, flt: FeedFilter = FeedFilter()
) -> list[FeedGame]:
    rows = conn.execute(
        """SELECT g.ics_uid, g.home_team = %s, g.game_type, h.name, a.name, g.start_utc, g.time_tbd,
                  g.venue, g.status, g.sequence, g.first_seen_at, g.updated_at
           FROM games g
           JOIN teams h ON h.abbr = g.home_team
           JOIN teams a ON a.abbr = g.away_team
           WHERE g.season = %s AND %s IN (g.home_team, g.away_team)
           ORDER BY g.start_utc, g.ics_uid""",
        (team, season, team),
    ).fetchall()
    games = [FeedGame(*r) for r in rows]
    return [g for g in games if flt.matches(g)]


def render_team_feed(
    team_name: str, games: list[FeedGame], flt: FeedFilter = FeedFilter()
) -> bytes:
    cal = icalendar.Calendar()
    cal.add("prodid", f"-//{APP_NAME}//{APP_NAME} NFL feed//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    title = f"{team_name} · {flt.label}" if flt.label else team_name
    cal.add("x-wr-calname", f"{title} ({APP_NAME})")
    cal.add("x-wr-timezone", "America/New_York")
    cal.add("refresh-interval", REFRESH_INTERVAL, parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", REFRESH_INTERVAL)

    cal.add_component(EASTERN_VTIMEZONE)
    for g in games:
        cal.add_component(_event(g))
    return cal.to_ical()


def _event(g: FeedGame) -> icalendar.Event:
    start_et = g.start_utc.astimezone(EASTERN)
    summary = f"{g.away_name} at {g.home_name}"
    if g.time_tbd:
        summary += " (time TBD)"
    if g.status == "cancelled":
        summary = f"CANCELLED: {summary}"

    ev = icalendar.Event()
    ev.add("uid", g.ics_uid)
    ev.add("sequence", g.sequence)
    ev.add("dtstamp", g.updated_at)
    ev.add("created", g.first_seen_at)
    ev.add("last-modified", g.updated_at)
    ev.add("summary", summary)

    if g.time_tbd:
        # All-day event on the scheduled Eastern date (#18 C).
        ev.add("dtstart", start_et.date())
        ev.add("dtend", start_et.date() + timedelta(days=1))
        kickoff = "Kickoff: time TBD"
    else:
        ev.add("dtstart", start_et)
        ev.add("dtend", start_et + GAME_DURATION)
        hour12 = start_et.hour % 12 or 12
        kickoff = f"Kickoff: {start_et:%a %b} {start_et.day}, {hour12}:{start_et:%M %p} ET"

    if g.venue:
        ev.add("location", g.venue)
    ev.add("description", "\n".join([
        kickoff,
        GAME_TYPE_LABELS.get(g.game_type, g.game_type),
        f"Schedule data: nflverse. Updates automatically via {APP_NAME}.",
    ]))
    ev.add("status", {"cancelled": "CANCELLED"}.get(g.status, "TENTATIVE" if g.time_tbd else "CONFIRMED"))
    # Games shouldn't mark the subscriber as busy.
    ev.add("transp", "TRANSPARENT")
    return ev
