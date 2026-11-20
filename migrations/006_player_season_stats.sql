-- 006: player season stats.
--
-- CollegeBasketballData's own season stats per player (usage, efficiency
-- ratings, shot-type detail) -- distinct from the stints-derived Ratings
-- built elsewhere from our own possession formula. The worker refreshes a
-- team-season's rows once they're missing or a few hours old (see worker.py's
-- sync_player_stats); payload is already translated into our field names
-- (sources/cbbd.py's to_player_advanced), so nothing else needs to know CBBD's.
--
-- No foreign key on athlete_id: a player can show up here (full roster, from
-- CBBD) before they show up in `players` (only populated from saved plays),
-- so the API just looks up what it can and leaves the rest out.

CREATE TABLE player_season_stats (
    team_id     text NOT NULL REFERENCES teams (id),
    season      int NOT NULL,
    athlete_id  text NOT NULL,
    payload     jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, season, athlete_id)
);
