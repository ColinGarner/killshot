"""Filling in incomplete on-floor lists from substitutions."""
import copy
import gzip
import json

from killshot import plays as P
from killshot.sources import cbbd
from killshot.substitutions import fill_lineups
from conftest import FIXTURES, KANSAS, KENTUCKY, load_data

GREEN_BAY_GAME, GREEN_BAY = "212779", "105"  # KU's 2025-26 opener, 94-51


def green_bay_data() -> dict:
    with gzip.open(FIXTURES / f"cbbd_{GREEN_BAY_GAME}.json.gz", "rt") as f:
        return json.load(f)


def test_the_green_bay_opener_had_no_kansas_lineup_at_tip_off_in_the_raw_data():
    # The problem this module solves: CBBD lists nobody for KU at the start.
    first = green_bay_data()["plays"][0]
    assert not [p for p in first["onFloor"] if p["team"] == "Kansas"]


def test_the_green_bay_opener_is_complete_after_filling():
    game = cbbd.to_game(green_bay_data())
    for team in (KANSAS, GREEN_BAY):
        q = game.quality(team)
        assert q["points_match"] and q["invalid_seconds"] == 0
        assert all(s.valid for s in game.stints[team])


def test_kansas_starters_are_worked_out_from_who_played_before_subbing_in():
    game = cbbd.to_game(green_bay_data())
    first = game.stints[KANSAS][0]
    starters = sorted(game.players[p].name for p in first.player_ids)
    assert starters == ["Darryn Peterson", "Flory Bidunga", "Kohl Rosario", "Melvin Council Jr.", "Tre White"]
    assert first.t_start == 0


def test_erasing_kansas_lineups_from_a_clean_game_gets_them_back():
    clean = cbbd.to_game(load_data(KENTUCKY))
    data = copy.deepcopy(load_data(KENTUCKY))
    for play in data["plays"][:150]:  # roughly the first 8 minutes
        play["onFloor"] = [p for p in play["onFloor"] if p["team"] != "Kansas"]
    rebuilt = cbbd.to_game(data)
    assert rebuilt.lineups_filled > 0
    assert rebuilt.quality(KANSAS)["points_match"]
    original, recovered = clean.minutes(KANSAS), rebuilt.minutes(KANSAS)
    assert original.keys() == recovered.keys()
    # Within 30 seconds each: CBBD sometimes switches its list a play after the
    # logged substitution, while the replay switches at the substitution itself.
    assert all(abs(original[p] - recovered[p]) < 0.5 for p in original)


def test_complete_lists_are_never_changed():
    raw = load_data(KENTUCKY)
    team_ids = {"Kansas": "131", "Kentucky": "135"}
    plays = [cbbd.to_play(p, team_ids) for p in raw["plays"]]
    before = [dict(p.on_floor) for p in plays]
    fill_lineups(plays, ["131", "135"])
    for b, play in zip(before, plays):
        for team, five in b.items():
            if len(five) == 5:
                assert play.on_floor[team] == five


def test_a_free_throw_between_two_subs_gets_the_five_from_the_end_of_that_moment():
    a, b = ("1", "2", "3", "4", "5"), ("1", "2", "3", "4", "6")
    plays = [
        P.Play(t=100, period=1, team_id="T", kind=P.SHOT, on_floor={"T": a}),
        P.Play(t=110, period=1, team_id="T", kind=P.SUB, sub="out", player_id="5", on_floor={"T": a[:4]}),
        P.Play(t=110, period=1, team_id="T", kind=P.FREE_THROW, made=True, points=1, on_floor={"T": a[:4]}),
        P.Play(t=110, period=1, team_id="T", kind=P.SUB, sub="in", player_id="6", on_floor={"T": b}),
    ]
    fill_lineups(plays, ["T"])
    assert plays[2].on_floor["T"] == b
