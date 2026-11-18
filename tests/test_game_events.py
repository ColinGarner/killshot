"""Killshots and win probability, checked against games we watched."""
from killshot import clock
from conftest import KANSAS, KENTUCKY, KENTUCKY_TEAM, UNLV


def test_kansas_12_0_killshot_against_kentucky(games):
    game = games[KENTUCKY]
    (run,) = game.runs
    assert run.team_id == KANSAS
    assert run.label == "12-0"
    assert clock.label(run.t0) == "2nd 18:35"
    assert clock.label(run.t1) == "2nd 15:00"
    # CBBD lists Kansas as the home team on the neutral floor: 51-41 became 63-41.
    assert (run.home0, run.away0, run.home1, run.away1) == (51, 41, 63, 41)


def test_unlv_had_no_killshots(games):
    assert games[UNLV].runs == []


def test_win_probability_flips_to_the_team_being_viewed(games):
    game = games[KENTUCKY]
    ku = [p.for_team(game.team(KANSAS).is_home) for p in game.win_prob]
    uk = [p.for_team(game.team(KENTUCKY_TEAM).is_home) for p in game.win_prob]
    assert ku[-1]["win_prob"] == 100 and uk[-1]["win_prob"] == 0
    # CBBD's own model: KU bottomed out at 41.4% early (ESPN's model said 49.6%).
    assert min(p["win_prob"] for p in ku) == 41.4


def test_clock_conversion_round_trips():
    assert clock.elapsed(1, "20:00") == 0
    assert clock.elapsed(2, "18:35") == 1285
    assert clock.elapsed(3, "4:00") == 2460  # one minute into overtime
    assert clock.label(1285) == "2nd 18:35"
    assert clock.elapsed(2, "45.5") == 2354.5
