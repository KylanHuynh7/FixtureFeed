"""Web app: team-choosing page and private ICS feed URLs (DECISIONS.md #5, #13, #18 E).

Run locally:
    uv run uvicorn fixturefeed.web:app --reload
"""

import hashlib
import secrets
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from importlib.resources import files

from fixturefeed.config import APP_NAME, CURRENT_SEASON
from fixturefeed.db import connect
from fixturefeed.feed import load_team_games, render_team_feed

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
def create_feed(team: Annotated[str, Form()], conn: Conn):
    if not conn.execute("SELECT 1 FROM teams WHERE abbr = %s", (team,)).fetchone():
        raise HTTPException(status_code=400, detail="Unknown team")
    token = secrets.token_urlsafe(16)  # 128 random bits
    with conn.transaction():
        conn.execute("INSERT INTO feeds (token, team_abbr) VALUES (%s, %s)", (token, team))
    return RedirectResponse(f"/feeds/{token}", status_code=303)


# Declared before the HTML route: both patterns would match "<token>.ics".
@app.get("/feeds/{token}.ics", name="team_feed")
def team_feed(token: str, request: Request, conn: Conn):
    team = _team_for_token(conn, token)
    body = render_team_feed(team[1], load_team_games(conn, team[0], CURRENT_SEASON))
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "private, max-age=300"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="text/calendar; charset=utf-8", headers=headers)


@app.get("/feeds/{token}", response_class=HTMLResponse)
def feed_page(token: str, request: Request, conn: Conn):
    abbr, name = _team_for_token(conn, token)
    https_url = str(request.url_for("team_feed", token=token))
    webcal_url = "webcal://" + https_url.split("://", 1)[1]
    return templates.TemplateResponse(
        request, "feed.html",
        {"team_name": name, "https_url": https_url, "webcal_url": webcal_url},
    )


def _team_for_token(conn, token: str) -> tuple[str, str]:
    row = conn.execute(
        """SELECT t.abbr, t.name FROM feeds f JOIN teams t ON t.abbr = f.team_abbr
           WHERE f.token = %s""",
        (token,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return row
