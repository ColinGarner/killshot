"""Lineup reconstruction must agree with ESPN's own box score."""
import pytest

from killshot import clock
from conftest import FORDHAM, KENTUCKY, MTSU, UNLV

ALL = [FORDHAM, MTSU, KENTUCKY, UNLV]


@pytest.mark.parametrize("event", ALL)
def test_stint_points_add_up_to_the_final_score_for_both_teams(games, event):
    game = games[event]
    for team in (game.home, game.away):
        assert game.quality(team.id)["points_match"], f"{team.abbr} in {event}"


@pytest.mark.parametrize("event", ALL)
def test_rebuilt_minutes_are_within_a_minute_and_a_half_of_the_box_score(games, event):
    # ESPN rounds box-score minutes to whole numbers, so ~1 minute of slack is expected.
    game = games[event]
    for team in (game.home, game.away):
        assert game.quality(team.id)["max_minutes_error"] <= 1.5, f"{team.abbr} in {event}"


@pytest.mark.parametrize("event", ALL)
def test_stints_cover_all_40_minutes_with_five_players(games, event):
    game = games[event]
    for team in (game.home, game.away):
        stints = game.stints[team.id]
        assert sum(s.seconds for s in stints) == 2 * clock.HALF
        assert all(s.valid for s in stints)
        # stints are back to back, no gaps or overlaps
        assert all(a.t_end == b.t_start for a, b in zip(stints, stints[1:]))


def test_garbage_time_flags_the_whole_second_half_of_a_blowout(games):
    # KU led Middle Tennessee by more than 20 at halftime and won 89-45.
    stints = games[MTSU].stints["2305"]
    garbage = sum(s.seconds for s in stints if s.garbage)
    assert garbage == clock.HALF


def test_a_close_first_half_is_never_garbage_time(games):
    stints = games[KENTUCKY].stints["2305"]
    assert not any(s.garbage for s in stints if s.t_end <= clock.HALF)
