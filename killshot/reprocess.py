"""Rebuild every stored game from its saved raw data, with the current code.

    killshot reprocess

Run it after a change to how stints, ratings or killshots are worked out.
Makes no API calls: it reads `games.raw`, which holds the provider's original data.
Games still waiting for their plays are skipped.
"""
import os

from . import db
from .sources import cbbd


def backfill_box_scores(conn) -> int:
    """Rebuild only the games saved before box scores existed (no API calls). Returns how many."""
    rows = db.games_missing_box_scores(conn)
    for game_id, raw in rows:
        db.save_game(conn, cbbd.to_game(raw), raw)
    return len(rows)


def main() -> None:
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        for name in db.migrate(conn):
            print(f"applied migration {name}")
        rows = conn.execute("SELECT id, raw FROM games WHERE plays_saved_at IS NOT NULL ORDER BY start_at").fetchall()
        for game_id, raw in rows:
            db.save_game(conn, cbbd.to_game(raw), raw)
        print(f"reprocessed {len(rows)} games")


if __name__ == "__main__":
    main()
