"""Box scores built from the plays match the official box score, player by player.

ESPN's summaries include its official box score, so each game checks itself:
Kentucky and UNLV (KU's 2026-27 opening week) and West Virginia (11/18).
"""
import gzip
import json
import os

import pytest

from killshot import db
from killshot.reprocess import backfill_box_scores
from killshot.sources import cbbd, espn
from conftest import FIXTURES, KANSAS, KENTUCKY, load_data
from test_espn_translation import ESPN_IDS, load_espn

WEST_VIRGINIA = "401920515"
FIELDS = ["pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf"]


def official(summary: dict) -> dict[str, dict]:
    """ESPN's box score: player name -> {pts, fgm, ...}."""
    out = {}
    for team in summary["boxscore"]["players"]:
        keys = team["statistics"][0]["keys"]
        for a in team["statistics"][0]["athletes"]:
            if not a["stats"]:
                continue  # didn't play
            s = dict(zip(keys, a["stats"]))
            fg, tp, ft = (s[k].split("-") for k in ("fieldGoalsMade-fieldGoalsAttempted",
                                                    "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
                                                    "freeThrowsMade-freeThrowsAttempted"))
            out[a["athlete"]["displayName"]] = dict(
                pts=int(s["points"]), fgm=int(fg[0]), fga=int(fg[1]), tpm=int(tp[0]), tpa=int(tp[1]),
                ftm=int(ft[0]), fta=int(ft[1]), oreb=int(s["offensiveRebounds"]), dreb=int(s["defensiveRebounds"]),
                ast=int(s["assists"]), stl=int(s["steals"]), blk=int(s["blocks"]), tov=int(s["turnovers"]),
                pf=int(s["fouls"]))
    return out


def ours(game) -> dict[str, dict]:
    return {game.players[l.player_id].name: {f: getattr(l, f) for f in FIELDS}
            for lines in game.box.values() for l in lines}


def with_stats(lines: dict[str, dict]) -> dict[str, dict]:
    """Leave out players with nothing in the box: ESPN and we disagree on whether to list a
    walk-on who played a few seconds, or a player listed with 0 minutes who never appears."""
    return {name: stats for name, stats in lines.items() if any(stats.values())}


def mismatches(game, summary) -> list[str]:
    truth, built = with_stats(official(summary)), with_stats(ours(game))
    assert set(built) == set(truth)
    return [f"{name} {f}: {built[name][f]} vs {truth[name][f]}"
            for name in truth for f in FIELDS if built[name][f] != truth[name][f]]


@pytest.mark.parametrize("event", [ESPN_IDS["372836"], WEST_VIRGINIA])
def test_live_box_score_matches_espns_official_one(event):
    summary = load_espn(event)
    assert mismatches(espn.to_game(summary), summary) == []


def test_the_only_kentucky_difference_is_one_assist_espns_box_score_corrected():
    # ESPN's play-by-play credits Momcilovic with 3 assists; its box score says 2.
    summary = load_espn(ESPN_IDS[KENTUCKY])
    assert mismatches(espn.to_game(summary), summary) == ["Milan Momcilovic ast: 3 vs 2"]


def test_cbbds_plays_give_the_same_box_score_as_espns():
    official_game = cbbd.to_game(load_data(KENTUCKY))
    assert ours(official_game) == ours(espn.to_game(load_espn(ESPN_IDS[KENTUCKY])))


def test_cbbd_shooter_is_read_from_the_play_text_not_the_list_order():
    # CBBD lists Kinney first on "Trey Kaufman-Renn makes ... (Taylen Kinney assists)".
    raw = next(p for p in load_data(KENTUCKY)["plays"]
               if p["playText"].startswith("Trey Kaufman-Renn makes 24-foot three"))
    assert raw["participants"][0]["name"] == "Taylen Kinney"
    play = cbbd.to_play(raw, {"Kansas": KANSAS, "Kentucky": "135"})
    assert (play.player_id, play.assist_id) == ("366", "224930")


def test_team_totals_add_up_to_the_final_score():
    game = espn.to_game(load_espn(WEST_VIRGINIA))
    for team in (game.home, game.away):
        assert sum(l.pts for l in game.box[team.id]) == team.score
        assert round(sum(l.minutes for l in game.box[team.id])) == 200  # five players, 40 minutes


URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")
def test_games_saved_before_box_scores_existed_are_filled_in(conn, games):
    db.save_game(conn, games[KENTUCKY], load_data(KENTUCKY))
    conn.execute("DELETE FROM player_games")  # as if saved by the old code
    assert backfill_box_scores(conn) == 1
    assert sum(l.pts for l in db.box_for_game(conn, KENTUCKY)[KANSAS]) == 89
    assert backfill_box_scores(conn) == 0  # nothing left to do
