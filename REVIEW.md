# Pending review

Decisions made by the engineer under the temporary delegation (DECISIONS.md #21).
None of these is approved. Each needs the director's explicit approval or reversal.

| # | Decision | Why | Alternative | Easy to reverse? |
|---|---|---|---|---|
| R1 | TBD rule marks only the **Sunday** games in a TBD week (Thu/Sat/Mon keep their listed times). | Those slots are announced separately; marking them TBD would hide real times. Same result for the 2026 schedule. | Mark the whole week TBD, as #18 C was worded. | Yes, one line in `sources/nflverse.py`. |
| R2 | A small runnable entry point: `uv run python -m fixturefeed.ingest [FILE]`, fetching with Python's built-in `urllib`. | Something has to run the pipeline; built-in library means no new dependency. | A command-line tool via `[project.scripts]`, or `httpx` as a dependency. | Yes. |
| R3 | Ingests are serialized with a Postgres advisory lock. | Two overlapping runs could otherwise both plan against the same old state and double-apply changes. | No lock (rely on running one at a time). | Yes. |
| R4 | Unknown team abbreviations reject the whole snapshot. | Safer than inserting half a schedule; a renamed team would show up as a clear rejection reason. | Skip only the affected rows. | Yes. |
| R5 | If a source ID (e.g. date-based `pfr`) gets reused by a different game, it is re-pointed to the newest game. | IDs can be recycled after reschedules; newest snapshot is the truth. Matching never uses `pfr`, so this only affects stored metadata. | Keep the first mapping and ignore the new one. | Yes. |
| R6 | Change-log format: one summary row for created/cancelled/restored, plus one `updated` row per changed field. | Easy to query for the future change-history page. | One row per change with a JSON blob of all fields. | Yes before launch; harder after real history accumulates. |
| R7 | Raw snapshots are saved to `data/snapshots/` (gitignored) on every run, including rejected ones. | A rejected file is exactly what you need to debug a rejection. | Save accepted snapshots only. | Yes. |
| R8 | `CURRENT_SEASON = 2026` constant in `config.py`; only that season is ingested and served. | MVP needs one season; the file contains 1999–2026. | Ingest all seasons. | Yes. |
| R9 | Round-trip parser: `vobject` (dev-only dependency). | Shares no code with `icalendar`, so the test is a real independent check. It already caught a real time-zone interoperability issue (R10). | `ics` (ics-py). | Yes. |
| R10 | Hand-written, rule-based `VTIMEZONE` for America/New_York instead of the library-generated one. | The generated block lists every 1970–2037 transition; `vobject` misread it (Oct 8 kickoff came out as UTC−5). The rule form is what Google/Apple emit. Correct for all dates since 2007. | Keep the generated block and ignore the `vobject` result (dateutil read it correctly). | Yes. |
| R11 | Event content: title "Away at Home" with full team names; "(time TBD)" suffix; "CANCELLED: " prefix; description has ET kickoff, round, and nflverse credit; location = stadium. Week number deliberately NOT shown (week changes don't bump SEQUENCE, so a shown week could go stale in clients). | Readable on phones; ET shown per #19; credit per #20. | Abbreviations ("TB @ DAL"); include week. | Yes. |
| R12 | Timed events last 3h30m. | Typical NFL game length incl. pregame; source has no end time. | 3h; or no DTEND (clients default to 1h or 0). | Yes, one constant. |
| R13 | TBD games are `STATUS:TENTATIVE`; all events `TRANSP:TRANSPARENT` (don't show subscriber as busy). | Games are informational, not meetings. | CONFIRMED for everything; OPAQUE (busy). | Yes. |
| R14 | `DTSTAMP` = the game's last change time, not "now". | Feed bytes are identical until something changes, which makes caching and testing simple. | DTSTAMP = generation time (also RFC-valid). | Yes. |
| R15 | `REFRESH-INTERVAL`/`X-PUBLISHED-TTL` = 6 hours. | A hint for Apple/Outlook; Google ignores it. Shorter means more requests to our server. | 1h, 12h, or omit. | Yes. |
| R16 | `python-multipart` (runtime) for the team form, `httpx2` (dev) for FastAPI's test client. `httpx` was tried first but Starlette now flags it as deprecated for the test client. | Standard FastAPI companions; no hand-rolled form parsing. | Parse the form body manually with `urllib.parse` (no dependency). | Yes. |
| R17 | Web routes: `GET /` (pick team), `POST /feeds` (create, 303 redirect), `GET /feeds/<token>` (link page with https + `webcal://` links), `GET /feeds/<token>.ics` (feed with ETag/304, `Cache-Control: private, max-age=300`). Unknown token → 404. | Minimal MVP surface; ETag lets well-behaved clients skip unchanged downloads. | Return the link directly on the same page without a redirect. | Yes. |
| R18 | A new database connection per request (no pool). | Simplest correct option for local MVP traffic. | psycopg connection pool (needs `psycopg-pool`). Worth revisiting before deploy. | Yes. |
| R19 | Page design: one small inline stylesheet with light/dark mode; copy says times are ET and that Google can take 12–24h to refresh. | Bare-bones per #5, but honest about polling delays. | Unstyled HTML. | Yes. |
| R20 | Replaced the one-line `README.md` with setup/run instructions and a short architecture summary. | Reviewers and interviewers read the README first. | Keep README minimal until polish phase. | Yes (git history). |
