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


# --- player season stats -----------------------------------------------------

def raw_player_season_stat() -> dict:
    """One CBBD /stats/player/season record, shaped like a real one."""
    return {
        "teamId": 131, "athleteId": 5642, "name": "Tre White", "games": 5, "starts": 5,
        "minutes": 129, "points": 97, "assists": 6, "turnovers": 4, "steals": 3, "blocks": 1, "fouls": 3,
        "usage": 27.5, "offensiveRating": 141.1, "defensiveRating": 95.3, "netRating": 45.8, "PORPAG": 6.2,
        "effectiveFieldGoalPct": 64.8, "trueShootingPct": 0.678, "assistsTurnoverRatio": 1.5,
        "freeThrowRate": 39.3, "offensiveReboundPct": 31.8,
        "fieldGoals": {"made": 34, "attempted": 61, "pct": 55.7},
        "twoPointFieldGoals": {"made": 23, "attempted": 37, "pct": 62.2},
        "threePointFieldGoals": {"made": 11, "attempted": 24, "pct": 45.8},
        "freeThrows": {"made": 18, "attempted": 24, "pct": 75},
        "rebounds": {"offensive": 7, "defensive": 15, "total": 22},
        "winShares": {"offensive": 0.7, "defensive": 0.3, "total": 1, "totalPer40": 0.31},
    }


def test_player_advanced_is_keyed_by_team_and_athlete():
    row = cbbd.to_player_advanced(raw_player_season_stat())
    assert (row["team_id"], row["athlete_id"]) == ("131", "5642")
    assert (row["games"], row["points"], row["porpag"]) == (5, 97, 6.2)
    assert row["win_shares"] == {"offensive": 0.7, "defensive": 0.3, "total": 1, "total_per_40": 0.31}
    assert row["field_goals"] == {"made": 34, "attempted": 61, "pct": 55.7}


def test_player_advanced_tolerates_missing_sub_objects():
    raw = raw_player_season_stat()
    del raw["rebounds"], raw["winShares"], raw["fieldGoals"]
    row = cbbd.to_player_advanced(raw)
    assert row["rebounds"] == {"offensive": 0, "defensive": 0, "total": 0}
    assert row["field_goals"] == {"made": 0, "attempted": 0, "pct": None}
