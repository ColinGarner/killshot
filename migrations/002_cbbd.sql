-- 002: switch to CollegeBasketballData.com as the data source.
--
-- Ids in every table are now CBBD's (Kansas is '131', not ESPN's '2305').
-- The data stored so far came from ESPN with ESPN ids, so it's cleared; run
-- `python -m killshot.load` again to reload from CBBD. games.raw now holds
-- CBBD's game record and plays: {"game": {...}, "plays": [...]}.

TRUNCATE teams, players, games, stints, win_prob, runs;

-- The same game's ESPN event id (CBBD calls it sourceId), for cross-checking.
ALTER TABLE games ADD COLUMN espn_id text;

-- CBBD doesn't send these with games or plays; nothing uses them yet.
ALTER TABLE players DROP COLUMN position;
ALTER TABLE teams DROP COLUMN abbr, DROP COLUMN color;

-- CBBD calls per calendar month (Tier 1 allows 5,000), so the worker can slow
-- down before running out.
CREATE TABLE api_usage (
    month  text PRIMARY KEY,           -- '2026-11'
    calls  int  NOT NULL DEFAULT 0
);
