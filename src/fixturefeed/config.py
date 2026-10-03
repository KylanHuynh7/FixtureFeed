"""Project-wide settings."""

# Display name used everywhere in the UI and feed metadata. Change it here only.
APP_NAME = "FixtureFeed"

# Suffix of every calendar event UID ("<uuid>@<suffix>"). Deliberately separate
# from APP_NAME: changing it would give every event a new UID, so calendars
# would show each game twice. Never change it after launch.
ICS_UID_SUFFIX = "fixturefeed"
