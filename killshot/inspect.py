"""Print one game the way the dashboard shows it.

    python -m killshot.inspect 401909786              # fetch from ESPN
    python -m killshot.inspect tests/fixtures/401909786.json.gz
    python -m killshot.inspect 401909786 --team 96    # Kentucky's side
"""
import argparse
import gzip
import json
from pathlib import Path

from . import espn, rollup
from .game import Game

KANSAS = "2305"


def load(source: str) -> dict:
    path = Path(source)
    if path.exists():
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as f:
            return json.load(f)
    return espn.summary(source)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game", help="ESPN event id or path to a saved summary")
    ap.add_argument("--team", help="team id to view the game from (default: Kansas if playing, else home)")
    ap.add_argument("--min-poss", type=float, default=3, help="possessions for a lineup to qualify")
    args = ap.parse_args()

    game = Game.from_summary(load(args.game))
    team_id = args.team or (KANSAS if KANSAS in (game.home.id, game.away.id) else game.home.id)
    team, opp = game.team(team_id), game.opponent(team_id)
    names = {pid: p.short_name for pid, p in game.players.items()}

    print(f"\n{team.name} {team.score}, {opp.name} {opp.score}  ({game.status})")
    q = game.quality(team_id)
    print(f"Reconstruction: points match = {q['points_match']}, "
          f"worst minutes error = {q['max_minutes_error']} min, unassigned time = {q['invalid_seconds']} s")

    rows = rollup.lineups(game.stints[team_id])
    best, worst = rollup.best_and_worst(rows, min_poss=args.min_poss)
    for title, group in (("Most efficient lineups", best), ("Least efficient lineups", worst)):
        print(f"\n{title} ({args.min_poss:g}+ possessions)")
        for r in group:
            lineup = " · ".join(sorted(names.get(p, p) for p in r["player_ids"]))
            print(f"  {lineup:<52} {r['minutes']:>5} min {r['poss']:>5} poss {r['plus_minus']:>+4} {r['net']:>+7.1f} net")
        if not group:
            print("  (none qualify)")

    print("\nKillshots (10-0 runs)")
    from .clock import label
    for run in game.runs:
        who = game.team(run.team_id).abbr
        print(f"  {who} {run.label}  {label(run.t0)} to {label(run.t1)}  "
              f"{run.home0}-{run.away0} -> {run.home1}-{run.away1} (home-away)")
    if not game.runs:
        print("  (none)")

    if game.win_prob:
        view = [p.for_team(team.is_home) for p in game.win_prob]
        low = min(view, key=lambda p: p["win_prob"])
        print(f"\nWin probability: start {view[0]['win_prob']}%, low {low['win_prob']}% at {low['clock']}, "
              f"end {view[-1]['win_prob']}%")


if __name__ == "__main__":
    main()
