"""Web app: team-choosing page and private ICS feed URLs (DECISIONS.md #5, #13, #18 E).

Run locally:
    uv run uvicorn fixturefeed.web:app --reload
"""

import hashlib
import secrets
from datetime import datetime, timezone
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from importlib.resources import files

from fixturefeed.atom import render_atom
from fixturefeed.config import APP_NAME, CURRENT_SEASON
from fixturefeed.db import connect
from fixturefeed.feed import FeedFilter, format_et, load_team_games, render_team_feed
from fixturefeed.history import first_snapshot, load_team_history

app = FastAPI(title=APP_NAME)
templates = Jinja2Templates(directory=str(files("fixturefeed").joinpath("templates")))
templates.env.globals["app_name"] = APP_NAME


def get_conn() -> Iterator[psycopg.Connection]:
    with connect() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


@app.get("/", response_class=HTMLResponse)
def choose_team(request: Request, conn: Conn):
    teams = conn.execute("SELECT abbr, name FROM teams ORDER BY name").fetchall()
    return templates.TemplateResponse(request, "index.html", {"teams": teams})


@app.post("/feeds")
def create_feed(
    team: Annotated[str, Form()],
    conn: Conn,
    side: Annotated[str, Form()] = "all",
    primetime_only: Annotated[bool, Form()] = False,
):
    if not conn.execute("SELECT 1 FROM teams WHERE abbr = %s", (team,)).fetchone():
        raise HTTPException(status_code=400, detail="Unknown team")
    if side not in ("all", "home", "away"):
        raise HTTPException(status_code=400, detail="Unknown filter")
    token = secrets.token_urlsafe(16)  # 128 random bits
    with conn.transaction():
        conn.execute(
            "INSERT INTO feeds (token, team_abbr, side, primetime_only) VALUES (%s, %s, %s, %s)",
            (token, team, side, primetime_only),
        )
    return RedirectResponse(f"/feeds/{token}", status_code=303)


# Declared before the HTML route: both patterns would match "<token>.ics".
@app.get("/feeds/{token}.ics", name="team_feed")
def team_feed(token: str, request: Request, conn: Conn):
    abbr, name, flt = _feed_for_token(conn, token)
    body = render_team_feed(name, load_team_games(conn, abbr, CURRENT_SEASON, flt), flt)
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "private, max-age=300"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="text/calendar; charset=utf-8", headers=headers)


@app.get("/feeds/{token}", response_class=HTMLResponse)
def feed_page(token: str, request: Request, conn: Conn):
    abbr, name, flt = _feed_for_token(conn, token)
    https_url = str(request.url_for("team_feed", token=token))
    webcal_url = "webcal://" + https_url.split("://", 1)[1]
    return templates.TemplateResponse(
        request, "feed.html",
        {"team_name": name, "filter_label": flt.label, "team_abbr": abbr,
         "https_url": https_url, "webcal_url": webcal_url},
    )


@app.get("/teams/{abbr}/changes", response_class=HTMLResponse, name="team_changes")
def team_changes(abbr: str, request: Request, conn: Conn):
    name = _team_name(conn, abbr)
    first = first_snapshot(conn)
    entries = [
        {"title": e.title, "messages": e.messages, "kickoff_now": e.kickoff_now,
         "detected": format_et(e.detected_at)}
        for e in load_team_history(conn, abbr, CURRENT_SEASON)
    ]
    return templates.TemplateResponse(request, "changes.html", {
        "team_name": name, "season": CURRENT_SEASON, "entries": entries,
        "tracking_since": format_et(first[1]) if first else None,
        "atom_url": request.url_for("team_changes_atom", abbr=abbr),
    })


@app.get("/teams/{abbr}/changes.atom", name="team_changes_atom")
def team_changes_atom(abbr: str, request: Request, conn: Conn):
    name = _team_name(conn, abbr)
    first = first_snapshot(conn)
    body = render_atom(
        abbr, name, load_team_history(conn, abbr, CURRENT_SEASON, limit=50),
        page_url=str(request.url_for("team_changes", abbr=abbr)),
        self_url=str(request.url),
        fallback_updated=first[1] if first else datetime.now(timezone.utc),
    )
    return Response(body, media_type="application/atom+xml; charset=utf-8")


def _team_name(conn, abbr: str) -> str:
    row = conn.execute("SELECT name FROM teams WHERE abbr = %s", (abbr,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown team")
    return row[0]


def _feed_for_token(conn, token: str) -> tuple[str, str, FeedFilter]:
    row = conn.execute(
        """SELECT t.abbr, t.name, f.side, f.primetime_only
           FROM feeds f JOIN teams t ON t.abbr = f.team_abbr
           WHERE f.token = %s""",
        (token,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    abbr, name, side, primetime_only = row
    return abbr, name, FeedFilter(side, primetime_only)
