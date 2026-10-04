"""Atom feed of a team's schedule changes (DECISIONS.md #8: notifications).

Any feed reader (or a service like IFTTT) can watch this URL and alert the user
when a game moves. Built with the standard library; no account or third-party
service involved.
"""

from datetime import datetime
from xml.etree import ElementTree as ET

from fixturefeed.config import APP_NAME, ICS_UID_SUFFIX
from fixturefeed.history import HistoryEntry

ATOM_NS = "http://www.w3.org/2005/Atom"


def render_atom(
    team_abbr: str, team_name: str, entries: list[HistoryEntry],
    page_url: str, self_url: str, fallback_updated: datetime,
) -> bytes:
    ET.register_namespace("", ATOM_NS)
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    _text(feed, "id", f"tag:{ICS_UID_SUFFIX},2026:changes/{team_abbr}")
    _text(feed, "title", f"{team_name} schedule changes ({APP_NAME})")
    updated = entries[0].detected_at if entries else fallback_updated
    _text(feed, "updated", updated.isoformat())
    _link(feed, page_url, "alternate")
    _link(feed, self_url, "self")
    author = ET.SubElement(feed, f"{{{ATOM_NS}}}author")
    _text(author, "name", APP_NAME)

    for e in entries:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        # Stable per game per snapshot, so readers never show an entry twice.
        _text(entry, "id", f"tag:{ICS_UID_SUFFIX},2026:change/{e.entry_id}")
        _text(entry, "title", f"{e.title}: {e.messages[0]}")
        _text(entry, "updated", e.detected_at.isoformat())
        _link(entry, page_url, "alternate")
        body = " ".join(e.messages) + f" Now: {e.kickoff_now}."
        _text(entry, "content", body).set("type", "text")

    return ET.tostring(feed, encoding="utf-8", xml_declaration=True)


def _text(parent, tag, value) -> ET.Element:
    el = ET.SubElement(parent, f"{{{ATOM_NS}}}{tag}")
    el.text = value
    return el


def _link(parent, href, rel) -> None:
    ET.SubElement(parent, f"{{{ATOM_NS}}}link", href=href, rel=rel)
