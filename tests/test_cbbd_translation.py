"""CBBD's play format is translated into ours correctly, including its quirks."""
import copy

from killshot import plays as P
from killshot.sources import cbbd
from conftest import KENTUCKY, load_data

TEAM_IDS = {"Kansas": "131", "Kentucky": "135"}


def raw_plays():
    return load_data(KENTUCKY)["plays"]


def test_a_missed_free_throw_is_an_attempt_not_a_make():
    # CBBD labels every free throw "MadeFreeThrow", even misses.
    missed = next(p for p in raw_plays() if p["playType"] == "MadeFreeThrow" and not p["scoringPlay"])
    play = cbbd.to_play(missed, TEAM_IDS)
    assert play.kind == P.FREE_THROW and not play.made


def test_threes_are_recognized_from_shot_range():
    three = next(p for p in raw_plays() if (p.get("shotInfo") or {}).get("range") == "three_pointer")
    assert cbbd.to_play(three, TEAM_IDS).three


def test_time_counts_up_from_tip_off():
    first = cbbd.to_play(raw_plays()[0], TEAM_IDS)
    assert first.t == 0 and first.period == 1
    second_half = next(p for p in raw_plays() if p["period"] == 2)
    assert cbbd.to_play(second_half, TEAM_IDS).t >= 1200


def test_every_play_lists_five_players_per_team():
    for raw in raw_plays():
        on_floor = cbbd.to_play(raw, TEAM_IDS).on_floor
        assert sorted(on_floor) == ["131", "135"]
        assert all(len(five) == 5 for five in on_floor.values())


def test_a_game_without_win_probability_still_loads():
    # Houston at Kansas (2025-26) has no win probability in CBBD at all.
    data = copy.deepcopy(load_data(KENTUCKY))
    for p in data["plays"]:
        p["homeWinProbability"] = None
    game = cbbd.to_game(data)
    assert game.win_prob == []
    assert game.quality("131") == {**game.quality("131"), "has_win_prob": False, "points_match": True}
