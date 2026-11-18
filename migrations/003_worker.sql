-- 003: what the worker needs to keep games up to date on its own.
--
-- The worker now stores every scheduled game as soon as it sees it, with only
-- CBBD's game record in raw ({"game": {...}}). After the final it fetches the
-- plays and stores the full {"game": ..., "plays": [...]}.

ALTER TABLE games
    ADD COLUMN plays_saved_at      timestamptz,             -- when CBBD's plays were stored; null until then
    ADD COLUMN plays_checks        int NOT NULL DEFAULT 0,  -- times we asked CBBD for plays and got none
    ADD COLUMN next_plays_check_at timestamptz;             -- when to ask again

-- Games loaded before this migration already have their plays.
UPDATE games SET plays_saved_at = saved_at WHERE raw ? 'plays';

-- One row: proof the worker is alive, and when it last refreshed schedules.
CREATE TABLE worker_status (
    id                     int PRIMARY KEY CHECK (id = 1),
    heartbeat_at           timestamptz NOT NULL,
    last_schedule_sync_at  timestamptz,
    note                   text                             -- what the last loop did, for logs and the health check
);
