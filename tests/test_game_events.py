"""Killshots and win probability, checked against games we watched."""
from killshot import clock
from conftest import KANSAS, KENTUCKY, UNLV


def test_kansas_12_0_killshot_against_kentucky(games):
    game = games[KENTUCKY]
    (run,) = game.runs
    assert run.team_id == KANSAS
    assert run.label == "12-0"
    assert clock.label(run.t0) == "2nd 18:35"
    assert clock.label(run.t1) == "2nd 15:00"
    # Kentucky was the home team on the neutral floor: 41-51 became 41-63.
    assert (run.home0, run.away0, run.home1, run.away1) == (41, 51, 41, 63)


def test_unlv_had_no_killshots(games):
    assert games[UNLV].runs == []


def test_win_probability_flips_to_the_team_being_viewed(games):
    game = games[KENTUCKY]
    ku_is_home = game.team(KANSAS).is_home
    ku = [p.for_team(ku_is_home) for p in game.win_prob]
    uk = [p.for_team(not ku_is_home) for p in game.win_prob]
    assert ku[-1]["win_prob"] == 100.0 and uk[-1]["win_prob"] == 0.0
    assert min(p["win_prob"] for p in ku) == 49.6  # KU's lowest point, 1st half 12:32


def test_clock_conversion_round_trips():
    assert clock.elapsed(1, "20:00") == 0
    assert clock.elapsed(2, "18:35") == 1285
    assert clock.elapsed(3, "4:00") == 2460  # one minute into overtime
    assert clock.label(1285) == "2nd 18:35"
    assert clock.elapsed(2, "45.5") == 2354.5
