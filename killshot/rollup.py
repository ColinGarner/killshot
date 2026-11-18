"""Add stints up into lineup tables, on/off splits and team totals.

Works the same for one game or a whole season: pass in whatever stints you want
counted. Invalid stints (not exactly five players) are skipped, and garbage time
can be excluded.
"""
from collections import defaultdict

from .box import Box, ratings
from .stints import Stint


def _usable(stints: list[Stint], exclude_garbage: bool) -> list[Stint]:
    return [s for s in stints if s.valid and not (exclude_garbage and s.garbage)]


def team_totals(stints: list[Stint], exclude_garbage: bool = False) -> dict | None:
    """Ratings for everything the team played in these stints."""
    use = _usable(stints, exclude_garbage)
    team, opp = sum((s.team for s in use), Box()), sum((s.opp for s in use), Box())
    return ratings(team, opp, sum(s.seconds for s in use))


def lineups(stints: list[Stint], exclude_garbage: bool = False) -> list[dict]:
    """One row per distinct five-man unit, with its combined ratings."""
    groups: dict[tuple, list[Stint]] = defaultdict(list)
    for s in _usable(stints, exclude_garbage):
        groups[s.player_ids].append(s)
    rows = []
    for ids, group in groups.items():
        r = ratings(sum((s.team for s in group), Box()), sum((s.opp for s in group), Box()),
                    sum(s.seconds for s in group))
        if r:
            rows.append({"player_ids": list(ids), "stints": len(group), **r})
    return rows


def best_and_worst(rows: list[dict], min_poss: float = 3, n: int = 5) -> tuple[list[dict], list[dict]]:
    """Split qualifying lineups into the top and bottom of the net-rating list, with no overlap."""
    q = sorted((r for r in rows if r["poss"] >= min_poss), key=lambda r: (-r["net"], -r["plus_minus"]))
    n_best = min(n, (len(q) + 1) // 2)
    n_worst = min(n, len(q) // 2)
    return q[:n_best], list(reversed(q[len(q) - n_worst:]))


def on_off(stints: list[Stint], exclude_garbage: bool = False) -> list[dict]:
    """For each player: team ratings with him on the floor vs. off it."""
    use = _usable(stints, exclude_garbage)
    total_team, total_opp = sum((s.team for s in use), Box()), sum((s.opp for s in use), Box())
    total_secs = sum(s.seconds for s in use)
    rows = []
    for pid in sorted({p for s in use for p in s.player_ids}):
        on = [s for s in use if pid in s.player_ids]
        on_team, on_opp = sum((s.team for s in on), Box()), sum((s.opp for s in on), Box())
        on_secs = sum(s.seconds for s in on)
        r_on = ratings(on_team, on_opp, on_secs)
        off_team = Box(**{k: total_team.as_dict()[k] - v for k, v in on_team.as_dict().items()})
        off_opp = Box(**{k: total_opp.as_dict()[k] - v for k, v in on_opp.as_dict().items()})
        r_off = ratings(off_team, off_opp, total_secs - on_secs)
        if r_on:
            rows.append({"player_id": pid, "on": r_on, "off": r_off,
                         "on_off": round(r_on["net"] - (r_off["net"] if r_off else 0), 1)})
    return rows
