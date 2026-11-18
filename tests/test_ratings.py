"""Ratings and rollups reproduce the numbers on the proof-of-concept dashboard."""
from killshot import rollup
from killshot.box import Box, possessions
from conftest import FORDHAM, KANSAS, KENTUCKY, MTSU


def test_possession_formula():
    team = Box(fga=60, oreb=10, to=12, fta=20)
    opp = Box(fga=58, oreb=8, to=14, fta=18)
    # (60-10+12+0.475*20 + 58-8+14+0.475*18) / 2
    assert possessions(team, opp) == (71.5 + 72.55) / 2


def test_first_three_games_team_ratings_match_the_dashboard(games):
    stints = [s for e in (FORDHAM, MTSU, KENTUCKY) for s in games[e].stints[KANSAS]]
    totals = rollup.team_totals(stints)
    assert (totals["ortg"], totals["drtg"], totals["net"]) == (122.7, 80.4, 42.2)


def test_excluding_garbage_time_changes_the_blowout_numbers(games):
    stints = games[MTSU].stints[KANSAS]
    full, competitive = rollup.team_totals(stints), rollup.team_totals(stints, exclude_garbage=True)
    assert competitive["minutes"] == 20.0
    assert full["net"] != competitive["net"]


def test_best_and_worst_lineups_never_overlap(games):
    rows = rollup.lineups(games[KENTUCKY].stints[KANSAS])
    best, worst = rollup.best_and_worst(rows, min_poss=3)
    assert best[0]["net"] == 133.9 and best[0]["plus_minus"] == 11
    assert not {tuple(r["player_ids"]) for r in best} & {tuple(r["player_ids"]) for r in worst}


def test_on_off_splits_add_back_to_the_team_total(games):
    stints = games[KENTUCKY].stints[KANSAS]
    total = rollup.team_totals(stints)
    for row in rollup.on_off(stints):
        on, off = row["on"], row["off"]
        assert on["pts"] + (off["pts"] if off else 0) == total["pts"]
