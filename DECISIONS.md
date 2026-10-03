# Decisions

Approved decisions only. Each entry records the director's approving words. Entries 1-10 were recorded on 2026-10-03 from the project kickoff message (approved before this session).

1. **Language: Python.** My words: "python"
2. **Sport scope: NFL first** (confirmed NFL, not college), then baseball, basketball, hockey as later expansions. My words: "lets actually do football and once we begin expanding sports we can do baseball, basketball, and then hockey" and "yes nfl is what i meant"
3. **Data source research spike authorized** (short, read-only). My words: "you have my ok"
   Spike limits: free sources only; check availability, stability, and terms of use; make a minimal number of requests, no scraping of anything behind a login or against stated terms; save sample responses locally. Also include a brief comparison of how Sync2Cal, FanSync, and similar products handle a schedule change, using only free, public information. Report options with tradeoffs and stop. Do not pick a source.
4. **Storage: Postgres.** My words: "postgres"
5. **MVP scope:** one team's feed that imports cleanly into Google and Apple Calendar, with stable UIDs and SEQUENCE numbers, plus a recorded-fixture test proving a changed game updates the existing event instead of duplicating it. A bare-bones team-choosing page is in. Filters, multi-team merging, notifications, and a second sport are out. My words: "agreed"
6. **Testing:** pytest, recorded real-world schedule snapshots as fixtures, unit tests on the diff logic, and a round-trip test parsing generated ICS with a third-party parser. Property-based tests later. My words: "agreed"
7. **Budget: $0.** My words: "i would rather just like to keep this as a $0 project"
8. **Differentiators after MVP, in order:** filters, then change-history page, then notifications. My words: "agreed"
9. **Dates:** MVP locally by Oct 23, 2026; deployed by Nov 20, 2026. My words: "those dates do work for me"
10. **Project name: FixtureFeed.** My words: "FixtureFeed sounds good to me"
11. **Data-source spike plan: Option A** (2026-10-03). Time-boxed (~1-2h), read-only. Sources: nflverse open data, ESPN public JSON endpoints, TheSportsDB; signup-gated free tiers (API-Sports, MySportsFeeds) from public docs only; NFL.com and Pro-Football-Reference terms read only. Per source: availability, auth, game-ID stability across reschedules, TBD/flex representation, freshness, rate limits, terms. Competitor comparison (Sync2Cal, FanSync, Calendar72, Sports Calendar Sync) from public pages only, no signups. Limits: ~3 data requests per source, ~20 total; curl and web fetch only; nothing installed; samples in `research/spike/samples/`; report in `research/SPIKE.md`; nothing committed; samples kept out of git until terms are checked. Report options, do not pick. My words: "option a sounds good to me"
12. **Data source: nflverse `games.csv` as the single source (Option A)** (2026-10-03), accessed behind a source adapter so it can be swapped later. Known gaps accepted: game IDs change when a game changes weeks, cancelled games disappear from the file, TBD times appear as placeholder times, and the repo has no stated license. How FixtureFeed handles each gap (own permanent IDs, treating a vanished game as cancelled, TBD inference) is NOT yet approved and needs its own proposal. My words: "option a, approved"
13. **Web framework: FastAPI**, with server-rendered HTML (Jinja2 templates) for the team-choosing page; served by uvicorn. (2026-10-03) My words: "the five setup decisions you have my approval to follow through with, install anything you may need for this project as well"
14. **Local Postgres: native via Homebrew, no Docker for now** (postgresql@17, run as a brew service). Revisit Docker at deploy time. (2026-10-03) Same approval as #13.
15. **ICS generation: `icalendar` library.** The round-trip test must parse with an independent parser; which one is not yet chosen. (2026-10-03) Same approval as #13.
16. **Python 3.13, managed with `uv`, with a committed lockfile (`uv.lock`).** (2026-10-03) Same approval as #13.
17. **Project structure: src layout** (`src/fixturefeed/`, `tests/`, `tests/fixtures/`). Detailed module design is a separate proposal. (2026-10-03) Same approval as #13.
