"""Stints must add up: to the final score, to 40 minutes, and to ESPN's box score."""
import json

import pytest

from killshot import clock
from conftest import FIXTURES, FORDHAM, KANSAS, KENTUCKY, MTSU, UNLV

ALL = [FORDHAM, MTSU, KENTUCKY, UNLV]


@pytest.mark.parametrize("game_id", ALL)
def test_stint_points_add_up_to_the_final_score_for_both_teams(games, game_id):
    game = games[game_id]
    for team in (game.home, game.away):
        assert game.quality(team.id)["points_match"], f"{team.name} in {game_id}"


@pytest.mark.parametrize("game_id", ALL)
def test_stints_cover_all_40_minutes_with_five_players(games, game_id):
    game = games[game_id]
    for team in (game.home, game.away):
        stints = game.stints[team.id]
        assert sum(s.seconds for s in stints) == 2 * clock.HALF
        assert all(s.valid for s in stints)
        # stints are back to back, no gaps or overlaps
        assert all(a.t_end == b.t_start for a, b in zip(stints, stints[1:]))


def test_minutes_match_espns_box_score_within_a_minute(games):
    # An independent check: ESPN's box score for the same game, matched by name.
    # ESPN rounds minutes to whole numbers, so up to ~1 minute apart is expected.
    box = json.loads((FIXTURES / "kentucky_box_minutes.json").read_text())["minutes"]
    game = games[KENTUCKY]
    for team in (game.home, game.away):
        for player_id, minutes in game.minutes(team.id).items():
            name = game.players[player_id].name
            assert abs(minutes - box[name]) <= 1.0, f"{name}: {minutes:.1f} vs box {box[name]}"


def test_garbage_time_flags_the_whole_second_half_of_a_blowout(games):
    # KU led Middle Tennessee by more than 20 at halftime and won 89-45.
    stints = games[MTSU].stints[KANSAS]
    assert sum(s.seconds for s in stints if s.garbage) == clock.HALF


def test_a_close_first_half_is_never_garbage_time(games):
    stints = games[KENTUCKY].stints[KANSAS]
    assert not any(s.garbage for s in stints if s.t_end <= clock.HALF)
