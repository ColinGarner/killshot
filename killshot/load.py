"""Load a team's finished games from CollegeBasketballData.com into Postgres.

    killshot load --team Kansas --seasons 2026 2027

Uses one API call per season plus one per new game. Safe to re-run: games
already saved as final are skipped unless you pass --refresh.
Needs DATABASE_URL, e.g. postgresql://killshot:killshot@localhost/killshot
"""
import argparse
import os
import time

from . import db
from .sources import cbbd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", default="Kansas", help="team name as CBBD spells it (default: Kansas)")
    ap.add_argument("--seasons", nargs="+", type=int, required=True, help="e.g. 2026 2027")
    ap.add_argument("--refresh", action="store_true", help="re-download games already saved")
    args = ap.parse_args()

    with db.connect(os.environ["DATABASE_URL"]) as conn:
        for name in db.migrate(conn):
            print(f"applied migration {name}")
        client = cbbd.Client(on_call=lambda: db.count_api_call(conn))
        already = set() if args.refresh else db.saved_final_game_ids(conn)

        for season in args.seasons:
            games = client.games(args.team, season)
            finished = [g for g in games if g["status"] == "final"]
            todo = [g for g in finished if str(g["id"]) not in already]
            print(f"{season}: {len(finished)} finished games, {len(todo)} to load")
            for n, record in enumerate(todo, 1):
                data = client.game_data(record)
                game = cbbd.to_game(data)
                db.save_game(conn, game, data)
                team_id = game.home.id if game.home.name == args.team else game.away.id
                q = game.quality(team_id)
                problems = [msg for ok, msg in ((q["points_match"], "points don't match"),
                                                (q["invalid_seconds"] == 0, "lineup gaps"),
                                                (q["has_win_prob"], "no win probability")) if not ok]
                print(f"  [{n}/{len(todo)}] {game.away.name} {game.away.score} @ {game.home.name} {game.home.score}"
                      + (f"  <- {', '.join(problems)}" if problems else ""))
                time.sleep(0.2)  # be polite

        print(f"CBBD calls this month: {db.api_calls_this_month(conn)} (Tier 1 limit 5,000)")


if __name__ == "__main__":
    main()
