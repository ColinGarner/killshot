"""Load a team's finished games from ESPN into Postgres.

    python -m killshot.load --team 2305 --seasons 2026 2027

Safe to re-run: games already saved as final are skipped unless you pass
--refresh. Needs DATABASE_URL, e.g. postgresql://killshot:killshot@localhost/killshot
"""
import argparse
import os
import time

from . import db, espn
from .game import Game


def finished_game_ids(team_id: str, season: int) -> list[str]:
    """ESPN event ids of a team's completed games, regular season then postseason."""
    ids = []
    for season_type in (2, 3):
        data = espn.schedule(team_id, season, season_type)
        for event in data.get("events", []):
            if event["competitions"][0]["status"]["type"]["completed"]:
                ids.append(event["id"])
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", default="2305", help="ESPN team id (default: Kansas)")
    ap.add_argument("--seasons", nargs="+", type=int, required=True, help="e.g. 2026 2027")
    ap.add_argument("--refresh", action="store_true", help="re-download games already saved")
    args = ap.parse_args()

    with db.connect(os.environ["DATABASE_URL"]) as conn:
        for name in db.migrate(conn):
            print(f"applied migration {name}")
        already = set() if args.refresh else db.saved_final_game_ids(conn)

        for season in args.seasons:
            ids = finished_game_ids(args.team, season)
            todo = [i for i in ids if i not in already]
            print(f"{season}: {len(ids)} finished games, {len(todo)} to load")
            for n, event_id in enumerate(todo, 1):
                raw = espn.summary(event_id)
                game = Game.from_summary(raw)
                db.save_game(conn, game, raw)
                q = game.quality(args.team)
                flag = "" if q["points_match"] and q["max_minutes_error"] <= 1.5 else "  <- check"
                print(f"  [{n}/{len(todo)}] {game.away.abbr} {game.away.score} @ {game.home.abbr} {game.home.score}"
                      f"  minutes error {q['max_minutes_error']}{flag}")
                time.sleep(0.5)  # be polite to ESPN


if __name__ == "__main__":
    main()
