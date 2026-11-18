-- 001: the first schema.
--
-- Games are stored from the home team's side (home_pts, home_wp), so one row
-- serves either team. Stints are stored per team, for BOTH teams in every game.
-- Time is "game seconds elapsed": 0 at tip, 1200 at half, 2400 end of regulation.

CREATE TABLE teams (
    id      text PRIMARY KEY,   -- ESPN team id; Kansas is '2305'
    name    text NOT NULL,      -- 'Kansas Jayhawks'
    abbr    text,               -- 'KU'
    color   text                -- ESPN's primary color, hex without '#'
);

CREATE TABLE players (
    id          text PRIMARY KEY,               -- ESPN athlete id, stable across seasons
    team_id     text REFERENCES teams (id),     -- most recent team we saw him play for
    name        text NOT NULL,                  -- 'Dennis Parker Jr.'
    short_name  text NOT NULL,                  -- 'Parker', used in lineup labels
    position    text
);

CREATE TABLE games (
    id            text PRIMARY KEY,             -- ESPN event id
    season        int  NOT NULL,                -- year the season ends: 2027 = 2026-27
    start_at      timestamptz NOT NULL,
    state         text NOT NULL CHECK (state IN ('pre', 'in', 'post')),
    status        text,                         -- ESPN's short status, e.g. 'Final'
    neutral_site  boolean NOT NULL DEFAULT false,
    home_team_id  text NOT NULL REFERENCES teams (id),
    away_team_id  text NOT NULL REFERENCES teams (id),
    home_pts      int,
    away_pts      int,
    raw           jsonb,                        -- ESPN's full game file; everything else can be rebuilt from it
    saved_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX games_by_home ON games (home_team_id, season);
CREATE INDEX games_by_away ON games (away_team_id, season);

-- One row per stretch with the same five players on the floor for one team.
-- The team_* columns are that team's stats during the stint; opp_* the opponent's.
CREATE TABLE stints (
    id          bigserial PRIMARY KEY,
    game_id     text NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    team_id     text NOT NULL REFERENCES teams (id),
    player_ids  text[] NOT NULL,                -- the five ESPN athlete ids, sorted
    t_start     real NOT NULL,
    t_end       real NOT NULL,
    garbage     boolean NOT NULL,               -- margin over 20 in the 2nd half or OT
    team_pts int NOT NULL, team_fga int NOT NULL, team_fgm int NOT NULL, team_tpa int NOT NULL, team_tpm int NOT NULL,
    team_fta int NOT NULL, team_ftm int NOT NULL, team_oreb int NOT NULL, team_dreb int NOT NULL, team_to int NOT NULL,
    opp_pts  int NOT NULL, opp_fga  int NOT NULL, opp_fgm  int NOT NULL, opp_tpa  int NOT NULL, opp_tpm  int NOT NULL,
    opp_fta  int NOT NULL, opp_ftm  int NOT NULL, opp_oreb  int NOT NULL, opp_dreb  int NOT NULL, opp_to  int NOT NULL
);
CREATE INDEX stints_by_team ON stints (team_id, game_id);
CREATE INDEX stints_by_player ON stints USING gin (player_ids);  -- "every stint with this player"

CREATE TABLE win_prob (
    game_id   text NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    t         int  NOT NULL,
    home_wp   real NOT NULL,                    -- home team's win probability, 0-100
    home_pts  int  NOT NULL,
    away_pts  int  NOT NULL,
    PRIMARY KEY (game_id, t)
);

-- Killshots: runs of 10+ unanswered points by either team.
CREATE TABLE runs (
    id       bigserial PRIMARY KEY,
    game_id  text NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    team_id  text NOT NULL REFERENCES teams (id),  -- the team on the run
    pts      int  NOT NULL,                        -- 12 means 12-0
    t0       int  NOT NULL,                        -- the other team's last score
    t1       int  NOT NULL,                        -- this team's last score of the run
    home0 int NOT NULL, away0 int NOT NULL,        -- score before
    home1 int NOT NULL, away1 int NOT NULL         -- score after
);
CREATE INDEX runs_by_game ON runs (game_id);
