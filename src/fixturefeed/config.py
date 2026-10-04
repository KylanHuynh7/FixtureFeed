"""Project-wide settings."""

# Display name used everywhere in the UI and feed metadata. Change it here only.
APP_NAME = "FixtureFeed"

# Suffix of every calendar event UID ("<uuid>@<suffix>"). Deliberately separate
# from APP_NAME: changing it would give every event a new UID, so calendars
# would show each game twice. Never change it after launch.
ICS_UID_SUFFIX = "fixturefeed"

# Season the pipeline ingests and serves.
CURRENT_SEASON = 2026

# nflverse schedule file (DECISIONS.md #12).
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# Raw snapshot files are kept here (gitignored); the database stores their hash.
SNAPSHOT_DIR = "data/snapshots"
