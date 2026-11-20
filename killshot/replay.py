"""Play back a finished game as if it were live, for testing the live view.

    killshot replay 372750                 # the Kentucky game (CBBD game id), about 80 seconds
    killshot replay 372750 --speed 10      # slower: 10 game-seconds per real second
    killshot replay 372750 --file espn.json.gz   # from a saved ESPN summary, no download
    killshot replay 372750 --keep          # leave the final live page in place at the end

Downloads ESPN's summary once, then every second moves the game clock forward,
cuts the plays off at that moment, builds the live page and saves it to
`live_state`, exactly as the worker does during a real game. At the end the
live row is deleted, so the game goes back to its normal finished page.

Also sends real push notifications (see push.py) for any killshot the replay
passes through, so `killshot replay` doubles as a way to test push alerts
end to end: subscribe in the browser, then run a replay and watch for them.
"""
import argparse
import gzip
import json
import os
import time
from pathlib import Path

from . import db, live, push
from .clock import elapsed, label
from .sources import espn


def load_summary(conn, game_id: str, path: str | None) -> dict:
    if path:
        opener = gzip.open if path.endswith(".gz") else open
        with opener(Path(path), "rt") as f:
            return json.load(f)
    event = db.espn_id(conn, game_id)
    if not event:
        raise SystemExit(f"Game {game_id} isn't in the database, or has no ESPN id. Try `killshot load` first.")
    return espn.summary(event)


def cut_points(summary: dict, step: float) -> list[int]:
    """How many plays the feed would have shown at each step of `step` game-seconds."""
    times = [elapsed(p["period"]["number"], p["clock"]["displayValue"]) for p in summary["plays"]]
    end = times[-1] if times else 0
    points, t = [], 0.0
    while t < end:
        points.append(sum(1 for x in times if x <= t))
        t += step
    return points + [len(times)]


def main() -> None:
    ap = argparse.ArgumentParser(prog="killshot replay", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game", help="CBBD game id, as in the site's game URL")
    ap.add_argument("--speed", type=float, default=30, help="game-seconds per real second (default 30)")
    ap.add_argument("--file", help="a saved ESPN summary (.json or .json.gz) instead of downloading")
    ap.add_argument("--keep", action="store_true", help="leave the final live page in place")
    args = ap.parse_args()

    with db.connect(os.environ["DATABASE_URL"]) as conn:
        db.migrate(conn)
        names = [t.strip() for t in os.environ.get("TRACKED_TEAMS", "Kansas").split(",") if t.strip()]
        rows = [(team_id, r) for team_id in db.team_ids(conn, names)
                for r in db.games_for_team(conn, team_id, game_id=args.game)]
        if not rows:
            raise SystemExit(f"Game {args.game} isn't a tracked team's game in the database.")
        summary = load_summary(conn, args.game, args.file)

        last_line = None
        try:
            for n in cut_points(summary, args.speed):
                game = espn.to_game(live.snapshot(summary, n))
                for team_id, row in rows:
                    prev = db.live_page(conn, args.game, team_id)
                    page = live.build(row, team_id, game)
                    team_name = row["home_name"] if row["home_team_id"] == team_id else row["away_name"]
                    for note in push.notify_new_killshots(conn, prev[0] if prev else None, page, team_name):
                        print(note, flush=True)
                    db.save_live(conn, args.game, team_id, page)
                g = page["game"]
                line = (f"{page['live']['clock'] or 'Tip-off':>10}  {g['pts']}-{g['opp_pts']} vs {g['opponent']['name']}"
                        f"  ({len(page['killshots'])} killshots)")
                if line != last_line:  # only when the clock or score moved
                    print(line, flush=True)
                    last_line = line
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            if not args.keep:
                db.clear_live(conn, args.game)
                print("Live row deleted; the game shows its finished page again.")
