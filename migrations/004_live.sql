-- 004: the live view.
--
-- While a game is on, the worker reads ESPN every 30 seconds and saves the
-- finished game page here, one row per tracked team in the game. The API
-- returns it as is. Rows are temporary: once CBBD's official record of the
-- game is saved, the row is deleted. Player ids inside payload are ESPN's.

CREATE TABLE live_state (
    game_id     text NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    team_id     text NOT NULL REFERENCES teams (id),   -- whose side the page is from
    payload     jsonb NOT NULL,                        -- the game page, as the API returns it
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, team_id)
);
