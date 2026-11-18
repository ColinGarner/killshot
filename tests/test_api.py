"""The web API, called the way the frontend will call it.

Uses a real Postgres (TEST_DATABASE_URL) holding KU's first four 2026-27 games.
"""
import pytest
from fastapi.testclient import TestClient

from killshot import db
from killshot.api import app
from conftest import FORDHAM, KANSAS, KENTUCKY, MTSU, UNLV, load_data


@pytest.fixture()
def api(conn, games, monkeypatch):
    """The API, pointed at a test database with four KU games and a fresh worker heartbeat."""
    for game_id in (FORDHAM, MTSU, KENTUCKY, UNLV):
        db.save_game(conn, games[game_id], load_data(game_id))
    db.heartbeat(conn, "ok; test")
    monkeypatch.setenv("DATABASE_URL", conn.info.dsn + " password=" + (conn.info.password or ""))
    monkeypatch.setenv("TRACKED_TEAMS", "Kansas")
    return TestClient(app)


def test_health_is_ok_with_a_fresh_worker_heartbeat(api):
    r = api.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"]


def test_health_fails_when_the_worker_has_gone_quiet(api, conn):
    conn.execute("UPDATE worker_status SET heartbeat_at = now() - interval '45 minutes'")
    r = api.get("/healthz")
    assert r.status_code == 503 and not r.json()["ok"]


def test_lists_the_tracked_teams(api):
    assert api.get("/api/teams").json() == [{"id": KANSAS, "name": "Kansas"}]


def test_only_tracked_teams_are_served(api):
    assert api.get("/api/teams/135/games", params={"season": 2027}).status_code == 404  # Kentucky


def test_the_schedule_is_from_kansas_side(api):
    games = api.get(f"/api/teams/{KANSAS}/games", params={"season": 2027}).json()
    assert [g["opponent"]["name"] for g in games] == ["Fordham", "Middle Tennessee", "Kentucky", "UNLV"]
    kentucky = games[2]
    assert (kentucky["pts"], kentucky["opp_pts"], kentucky["result"]) == (89, 69, "W")
    assert kentucky["has_plays"]


def test_an_upcoming_game_has_no_score_yet(api, conn):
    upcoming = {**load_data(UNLV)["game"], "id": 999003, "status": "scheduled", "startDate": "2026-12-01T01:00:00.000Z",
                "homePoints": 0, "awayPoints": 0}
    db.upsert_scheduled_game(conn, upcoming, "pre")
    game = [g for g in api.get(f"/api/teams/{KANSAS}/games", params={"season": 2027}).json() if g["id"] == "999003"][0]
    assert (game["state"], game["pts"], game["opp_pts"], game["result"], game["has_plays"]) == ("pre", None, None, None, False)


def test_a_game_has_lineups_win_probability_and_killshots(api):
    g = api.get(f"/api/teams/{KANSAS}/games/{KENTUCKY}").json()
    best = g["lineups"]["best"][0]
    assert best["net"] == 154.2 and best["plus_minus"] == 8
    assert sorted(p["short_name"] for p in best["players"]) == ["Blyden", "Dawes", "Kinney", "Stokes", "White"]
    assert "Leroy Blyden Jr." in [p["name"] for p in best["players"]]
    assert g["win_prob"][-1]["win_prob"] == 100 and min(p["win_prob"] for p in g["win_prob"]) == 41.4
    (shot,) = g["killshots"]
    assert shot == {**shot, "by": "team", "label": "12-0", "start": "2nd 18:35", "end": "2nd 15:00",
                    "score_before": [51, 41], "score_after": [63, 41]}


def test_an_unknown_game_is_a_404(api):
    assert api.get(f"/api/teams/{KANSAS}/games/123").status_code == 404


def test_season_totals_match_the_command_line(api):
    s = api.get(f"/api/teams/{KANSAS}/seasons/2027", params={"min_minutes": 10}).json()
    assert s["totals"]["net"] == 39.3  # all four games, the same as `killshot.season --season 2027`
    assert s["lineups"] and all(r["minutes"] >= 10 for r in s["lineups"])
    assert s["on_off"][0]["on_off"] >= s["on_off"][-1]["on_off"]


def test_excluding_garbage_time_changes_the_season(api):
    full = api.get(f"/api/teams/{KANSAS}/seasons/2027").json()["totals"]
    competitive = api.get(f"/api/teams/{KANSAS}/seasons/2027", params={"exclude_garbage": True}).json()["totals"]
    assert competitive["minutes"] < full["minutes"]
