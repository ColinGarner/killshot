"""Print a team's season from the database: team ratings, top lineups, on/off.

    python -m killshot.season --season 2026
    python -m killshot.season --season 2026 --no-garbage
"""
import argparse
import os

from . import db, rollup


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", default="131", help="CBBD team id (default: Kansas)")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--min-minutes", type=float, default=40)
    ap.add_argument("--no-garbage", action="store_true", help="leave out garbage time")
    args = ap.parse_args()

    with db.connect(os.environ["DATABASE_URL"]) as conn:
        stints = db.stints_for(conn, args.team, args.season)
        names = db.player_names(conn)
    if not stints:
        print("No games saved for that team and season. Run killshot.load first.")
        return

    t = rollup.team_totals(stints, exclude_garbage=args.no_garbage)
    print(f"\nTeam: ORtg {t['ortg']}  DRtg {t['drtg']}  Net {t['net']:+}  over {t['poss']:.0f} possessions")

    rows = [r for r in rollup.lineups(stints, exclude_garbage=args.no_garbage) if r["minutes"] >= args.min_minutes]
    print(f"\nLineups with {args.min_minutes:g}+ minutes, best first")
    for r in sorted(rows, key=lambda r: -r["net"]):
        lineup = " · ".join(sorted(names.get(p, p) for p in r["player_ids"]))
        print(f"  {lineup:<52} {r['minutes']:>6} min {r['poss']:>6} poss {r['net']:>+7.1f} net")

    print("\nOn/off (team net rating with the player on minus off), 100+ minutes")
    split = [r for r in rollup.on_off(stints, exclude_garbage=args.no_garbage) if r["on"]["minutes"] >= 100]
    for r in sorted(split, key=lambda r: -r["on_off"]):
        print(f"  {names.get(r['player_id'], r['player_id']):<16} {r['on']['minutes']:>6} min on  {r['on_off']:>+6.1f}")


if __name__ == "__main__":
    main()
