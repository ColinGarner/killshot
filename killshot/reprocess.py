"""Rebuild every stored game from its saved raw data, with the current code.

    python -m killshot.reprocess

Run it after a change to how stints, ratings or killshots are worked out.
Makes no API calls: it reads `games.raw`, which holds the provider's original data.
"""
import os

from . import db
from .sources import cbbd


def main() -> None:
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        for name in db.migrate(conn):
            print(f"applied migration {name}")
        rows = conn.execute("SELECT id, raw FROM games WHERE raw IS NOT NULL ORDER BY start_at").fetchall()
        for game_id, raw in rows:
            db.save_game(conn, cbbd.to_game(raw), raw)
        print(f"reprocessed {len(rows)} games")


if __name__ == "__main__":
    main()
