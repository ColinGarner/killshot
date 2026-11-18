"""The live game page, built from ESPN, and `killshot replay`.

Uses ESPN's summary of KU vs Kentucky: a neutral-site game where ESPN calls
Kentucky the home team and CBBD calls Kansas the home team.
"""
import datetime as dt
import os

import pytest

from killshot import db, live, schemas
from killshot.game import Game, Team
from killshot.replay import cut_points
from killshot.sources import espn
from conftest import KANSAS, KENTUCKY, load_data
from test_espn_translation import ESPN_IDS, load_espn

SUMMARY = load_espn(ESPN_IDS[KENTUCKY])

# Our games-table row for the game, as db.games_for_team returns it (CBBD: Kansas home).
ROW = {"id": KENTUCKY, "start_at": dt.datetime(2026, 11, 11, 2, 58, tzinfo=dt.timezone.utc), "time_tbd": False,
       "state": "in", "status": "In Progress", "neutral_site": True,
       "home_team_id": KANSAS, "home_name": "Kansas", "away_team_id": "135", "away_name": "Kentucky",
       "home_pts": 0, "away_pts": 0, "has_plays": False}


def page_after(n_plays: int | None = None) -> dict:
    data = SUMMARY if n_plays is None else live.snapshot(SUMMARY, n_plays)
    return live.build(ROW, KANSAS, espn.to_game(data))


# --- matching ESPN's teams to ours -------------------------------------------

def test_our_team_is_found_by_name_even_when_espn_flips_home_and_away():
    game = espn.to_game(SUMMARY)
    us = live.our_side(game, "Kansas", "Kentucky")
    assert us.name == "Kansas" and not us.is_home  # ESPN: Kentucky is home


def test_if_our_name_differs_the_opponent_identifies_us():
    game = Game("1", "1", 2027, "", "in", "", True,
                home=Team("2305", "Kansas Jayhawks", True, 0), away=Team("96", "Kentucky", False, 0))
    assert live.our_side(game, "Kansas", "Kentucky").id == "2305"
    with pytest.raises(ValueError):
        live.our_side(game, "Duke", "UNC")


# --- the page ----------------------------------------------------------------

def test_the_final_page_is_from_kansas_side():
    page = page_after()
    g = page["game"]
    assert (g["pts"], g["opp_pts"], g["result"], g["state"]) == (89, 69, "W", "post")
    assert page["win_prob"][-1]["win_prob"] == 100       # flipped from ESPN's home (Kentucky)
    (run,) = page["killshots"]
    assert (run["by"], run["label"], run["start"], run["score_before"]) == ("team", "12-0", "2nd 18:35", [51, 41])


def test_the_page_fits_the_api_response_model():
    # So 7.4 can return it as is; the extra `live` block is checked there.
    schemas.GameDetail.model_validate(page_after(250))


def test_midway_the_page_shows_the_game_so_far():
    page = page_after(250)
    last = SUMMARY["plays"][249]
    g = page["game"]
    assert g["state"] == "in" and g["result"] is None
    assert (g["pts"], g["opp_pts"]) == (last["awayScore"], last["homeScore"])  # Kansas is ESPN's away team
    assert page["live"]["clock"].startswith(("1st", "2nd"))
    assert len(page["live"]["on_floor"]) == 5
    assert all(p["name"] for p in page["live"]["on_floor"])


def test_before_any_plays_the_page_is_empty_but_valid():
    page = page_after(0)
    assert (page["game"]["pts"], page["game"]["opp_pts"]) == (0, 0)
    assert page["live"] == {**page["live"], "clock": None, "on_floor": []}
    assert page["lineups"] == {"best": [], "worst": []}


# --- replay ------------------------------------------------------------------

def test_replay_steps_through_the_whole_game_in_order():
    points = cut_points(SUMMARY, step=60)
    assert points[0] < points[1] and points == sorted(points)
    assert points[-1] == len(SUMMARY["plays"])
    assert 40 <= len(points) <= 42  # 40 game minutes, a step per minute


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_live_pages_save_update_and_clear(conn, games):
    db.save_game(conn, games[KENTUCKY], load_data(KENTUCKY))
    db.save_live(conn, KENTUCKY, KANSAS, page_after(100))
    db.save_live(conn, KENTUCKY, KANSAS, page_after(200))  # the next poll replaces it
    payload, updated_at = db.live_page(conn, KENTUCKY, KANSAS)
    assert payload == page_after(200) | {"live": payload["live"]}
    assert db.espn_id(conn, KENTUCKY) == ESPN_IDS[KENTUCKY]
    db.clear_live(conn, KENTUCKY)
    assert db.live_page(conn, KENTUCKY, KANSAS) is None
