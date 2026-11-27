-- 007: box scores. One row per player per game, for both teams, built from the
-- plays (see boxscore.py). Saved with the game, so it's replaced when the game is.

CREATE TABLE player_games (
    game_id     text NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    team_id     text NOT NULL REFERENCES teams (id),
    player_id   text NOT NULL,
    minutes     real NOT NULL,
    pts int NOT NULL, fgm int NOT NULL, fga int NOT NULL, tpm int NOT NULL, tpa int NOT NULL,
    ftm int NOT NULL, fta int NOT NULL, oreb int NOT NULL, dreb int NOT NULL, ast int NOT NULL,
    stl int NOT NULL, blk int NOT NULL, tov int NOT NULL, pf int NOT NULL,
    plus_minus  int NOT NULL,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX player_games_by_player ON player_games (player_id);
