-- FixtureFeed schema (DECISIONS.md #18). Single file, no migrations yet:
-- before deploy we add a migration tool. Applying this drops nothing; it
-- expects an empty database.

CREATE TABLE teams (
    abbr text PRIMARY KEY,          -- nflverse abbreviation, e.g. 'SF'
    name text NOT NULL
);

-- One row per real-world game. `id` and `ics_uid` are ours and never change,
-- even when the source renames, moves, or drops the game.
CREATE TABLE games (
    id            uuid PRIMARY KEY,
    ics_uid       text NOT NULL UNIQUE,
    season        integer NOT NULL,
    game_type     text NOT NULL,    -- REG, WC, DIV, CON, SB
    week          integer NOT NULL,
    home_team     text NOT NULL REFERENCES teams (abbr),
    away_team     text NOT NULL REFERENCES teams (abbr),
    start_utc     timestamptz NOT NULL,
    time_tbd      boolean NOT NULL DEFAULT false,
    venue         text,
    status        text NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled', 'cancelled')),
    sequence      integer NOT NULL DEFAULT 0,
    content_hash  text NOT NULL,    -- hash of calendar-visible fields only
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    -- NFL-specific natural key: verified unique across 1999-2026.
    -- Baseball/basketball/hockey repeat this combination within a season,
    -- so expanding sports must replace this constraint.
    UNIQUE (season, game_type, home_team, away_team)
);

-- Every ID a source has used for a game. Old IDs stay after a game moves,
-- so a renamed game still points at the same row.
CREATE TABLE game_source_ids (
    source      text NOT NULL,      -- e.g. 'nflverse'
    id_kind     text NOT NULL,      -- e.g. 'game_id', 'espn', 'gsis', 'pfr'
    external_id text NOT NULL,
    game_id     uuid NOT NULL REFERENCES games (id),
    PRIMARY KEY (source, id_kind, external_id)
);

-- Each fetched file, accepted or rejected. Raw files live on disk (gitignored).
CREATE TABLE snapshots (
    id            bigserial PRIMARY KEY,
    source        text NOT NULL,
    fetched_at    timestamptz NOT NULL,
    sha256        text NOT NULL,
    row_count     integer NOT NULL,
    accepted      boolean NOT NULL,
    reject_reason text,
    CHECK (accepted OR reject_reason IS NOT NULL)
);

-- Append-only log of every detected change; source of truth for tests and
-- the future change-history page.
CREATE TABLE game_changes (
    id          bigserial PRIMARY KEY,
    game_id     uuid NOT NULL REFERENCES games (id),
    snapshot_id bigint NOT NULL REFERENCES snapshots (id),
    change_type text NOT NULL,      -- created, updated, cancelled, restored
    field       text,               -- NULL for created/cancelled/restored
    old_value   text,
    new_value   text,
    changed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX game_changes_game_id_idx ON game_changes (game_id);

-- A private subscription URL: /feeds/<token>.ics. No user accounts.
CREATE TABLE feeds (
    id         bigserial PRIMARY KEY,
    token      text NOT NULL UNIQUE,
    team_abbr  text NOT NULL REFERENCES teams (abbr),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO teams (abbr, name) VALUES
    ('ARI', 'Arizona Cardinals'),     ('ATL', 'Atlanta Falcons'),
    ('BAL', 'Baltimore Ravens'),      ('BUF', 'Buffalo Bills'),
    ('CAR', 'Carolina Panthers'),     ('CHI', 'Chicago Bears'),
    ('CIN', 'Cincinnati Bengals'),    ('CLE', 'Cleveland Browns'),
    ('DAL', 'Dallas Cowboys'),        ('DEN', 'Denver Broncos'),
    ('DET', 'Detroit Lions'),         ('GB',  'Green Bay Packers'),
    ('HOU', 'Houston Texans'),        ('IND', 'Indianapolis Colts'),
    ('JAX', 'Jacksonville Jaguars'),  ('KC',  'Kansas City Chiefs'),
    ('LA',  'Los Angeles Rams'),      ('LAC', 'Los Angeles Chargers'),
    ('LV',  'Las Vegas Raiders'),     ('MIA', 'Miami Dolphins'),
    ('MIN', 'Minnesota Vikings'),     ('NE',  'New England Patriots'),
    ('NO',  'New Orleans Saints'),    ('NYG', 'New York Giants'),
    ('NYJ', 'New York Jets'),         ('PHI', 'Philadelphia Eagles'),
    ('PIT', 'Pittsburgh Steelers'),   ('SEA', 'Seattle Seahawks'),
    ('SF',  'San Francisco 49ers'),   ('TB',  'Tampa Bay Buccaneers'),
    ('TEN', 'Tennessee Titans'),      ('WAS', 'Washington Commanders');
