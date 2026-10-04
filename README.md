# FixtureFeed

Subscribable NFL team calendars. Pick a team, get a private ICS link, and add it
to Google or Apple Calendar. When a game is moved, flexed, or cancelled, the
existing calendar event is updated (same UID, higher SEQUENCE) instead of
duplicated.

Schedule data: [nflverse](https://github.com/nflverse/nfldata).

## Run locally

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), and PostgreSQL 17.

```sh
uv sync
createdb fixturefeed && createdb fixturefeed_test

# Create or upgrade tables (safe to re-run)
uv run python -m fixturefeed.db

# Download the current schedule and apply any changes
uv run python -m fixturefeed.ingest

# ...or keep it updated: re-check every 30 minutes (Ctrl-C to stop)
uv run python -m fixturefeed.ingest --every 30

# Start the web app at http://127.0.0.1:8000
uv run uvicorn fixturefeed.web:app --reload
```

`DATABASE_URL` overrides the default `postgresql:///fixturefeed`;
`FIXTUREFEED_TEST_DATABASE_URL` overrides the test database.

## Tests

```sh
uv run pytest
```

The test database is wiped on every run.

## How schedule changes are handled

1. `sources/nflverse.py` parses the CSV, converts Eastern kickoff times to UTC,
   and infers TBD weeks.
2. `diff.py` matches each game to our own permanent ID (season + type + home +
   away, with the ESPN ID as a backup) and plans creates, updates,
   cancellations, and restorations. SEQUENCE only increases when something a
   calendar shows has changed.
3. `store.py` applies the plan in one transaction and logs every change.
   Suspicious snapshots (shrunken, missing teams, ambiguous matches) are
   rejected without touching any game.
4. `feed.py` renders each team's games as ICS.

Project decisions are recorded in `DECISIONS.md`.
