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
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)  # don't inherit a developer's real .env
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


def test_on_off_carries_cbbd_advanced_stats_once_synced(api, conn):
    white_id = next(pid for pid, name in conn.execute("SELECT id, name FROM players").fetchall() if name == "Tre White")
    db.save_player_season_stats(conn, KANSAS, 2027, [{
        "team_id": KANSAS, "athlete_id": white_id, "games": 5, "starts": 5, "minutes": 129, "points": 97,
        "assists": 6, "turnovers": 4, "steals": 3, "blocks": 1, "fouls": 3, "usage": 27.5,
        "offensive_rating": 141.1, "defensive_rating": 95.3, "net_rating": 45.8, "porpag": 6.2,
        "effective_fg_pct": 64.8, "true_shooting_pct": 0.678, "assists_turnover_ratio": 1.5,
        "free_throw_rate": 39.3, "offensive_rebound_pct": 31.8,
        "field_goals": {"made": 34, "attempted": 61, "pct": 55.7},
        "two_point_field_goals": {"made": 23, "attempted": 37, "pct": 62.2},
        "three_point_field_goals": {"made": 11, "attempted": 24, "pct": 45.8},
        "free_throws": {"made": 18, "attempted": 24, "pct": 75},
        "rebounds": {"offensive": 7, "defensive": 15, "total": 22},
        "win_shares": {"offensive": 0.7, "defensive": 0.3, "total": 1, "total_per_40": 0.31},
    }])
    on_off = api.get(f"/api/teams/{KANSAS}/seasons/2027").json()["on_off"]
    by_name = {r["player"]["name"]: r for r in on_off}
    assert by_name["Tre White"]["advanced"]["porpag"] == 6.2
    assert by_name["Tre White"]["advanced"]["field_goals"] == {"made": 34, "attempted": 61, "pct": 55.7}
    assert all(r["advanced"] is None for name, r in by_name.items() if name != "Tre White")


# --- serving the frontend (no database needed) -----------------------------------

@pytest.fixture()
def site(tmp_path, monkeypatch):
    """The API serving a tiny stand-in for the built frontend."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log('app')")
    monkeypatch.setenv("WEB_DIST", str(tmp_path))
    return TestClient(app)


def test_page_urls_get_the_react_app(site):
    for path in ("/", "/games", "/games/372750"):
        r = site.get(path)
        assert r.status_code == 200 and "id=root" in r.text, path


def test_built_assets_are_served_and_cached_for_good(site):
    r = site.get("/assets/app-abc123.js")
    assert r.text == "console.log('app')"
    assert "immutable" in r.headers["cache-control"]


def test_a_missing_asset_is_a_404_not_the_app(site):
    # An old tab asking for a script from a previous build must not get HTML back.
    r = site.get("/assets/app-old999.js")
    assert r.status_code == 404 and "id=root" not in r.text


def test_the_app_page_is_never_cached(site):
    assert site.get("/games").headers["cache-control"] == "no-cache"


def test_unknown_api_paths_stay_404s_not_the_app(site):
    r = site.get("/api/nope")
    assert r.status_code == 404 and "id=root" not in r.text


def test_files_outside_the_build_folder_are_never_served(site):
    r = site.get("/..%2F..%2Fpyproject.toml")
    assert "killshot" not in r.text  # falls back to the app, not the file


# --- live games --------------------------------------------------------------

from killshot import live  # noqa: E402
from killshot.sources import espn  # noqa: E402
from test_espn_translation import ESPN_IDS, load_espn  # noqa: E402


def go_live(conn, n_plays: int) -> None:
    """Save Kentucky's live page as the worker would, after `n_plays` plays."""
    (row,) = db.games_for_team(conn, KANSAS, game_id=KENTUCKY)
    game = espn.to_game(live.snapshot(load_espn(ESPN_IDS[KENTUCKY]), n_plays))
    db.save_live(conn, KENTUCKY, KANSAS, live.build(row, KANSAS, game))


def test_a_live_game_page_comes_from_the_live_feed(api, conn):
    go_live(conn, 250)
    g = api.get(f"/api/teams/{KANSAS}/games/{KENTUCKY}").json()
    assert g["game"]["live"] and g["game"]["state"] == "in" and g["game"]["result"] is None
    assert g["live"]["clock"].startswith(("1st", "2nd")) and len(g["live"]["on_floor"]) == 5
    assert g["live"]["updated_at"]
    assert g["game"]["pts"] < 89  # the score so far, not the final


def test_the_game_list_shows_the_live_score(api, conn):
    go_live(conn, 250)
    games = api.get(f"/api/teams/{KANSAS}/games", params={"season": 2027}).json()
    kentucky, others = games[2], games[:2] + games[3:]
    assert kentucky["live"] and kentucky["state"] == "in" and kentucky["pts"] < 89
    assert not any(g["live"] for g in others)


def test_once_the_live_page_is_cleared_the_official_page_returns(api, conn):
    go_live(conn, 250)
    db.clear_live(conn, KENTUCKY)
    g = api.get(f"/api/teams/{KANSAS}/games/{KENTUCKY}").json()
    assert g["live"] is None and not g["game"]["live"] and g["game"]["pts"] == 89


# --- push notifications -------------------------------------------------------

def test_the_vapid_key_is_none_until_its_configured(api):
    assert api.get("/api/push/vapid-key").json() == {"public_key": None}


def test_the_vapid_key_is_served_once_set(api, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "a-test-key")
    assert api.get("/api/push/vapid-key").json() == {"public_key": "a-test-key"}


def test_subscribing_and_unsubscribing(api, conn):
    body = {"endpoint": "https://push.example/sub", "keys": {"p256dh": "p", "auth": "a"}}
    r = api.post("/api/push/subscribe", json=body)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert [s["endpoint"] for s in db.push_subscriptions(conn)] == [body["endpoint"]]

    r = api.post("/api/push/unsubscribe", json={"endpoint": body["endpoint"]})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert db.push_subscriptions(conn) == []


def test_a_game_has_both_teams_box_scores_kansas_first(api):
    box = api.get(f"/api/teams/{KANSAS}/games/{KENTUCKY}").json()["box"]
    assert [b["team"]["name"] for b in box] == ["Kansas", "Kentucky"]
    assert (box[0]["totals"]["pts"], box[1]["totals"]["pts"]) == (89, 69)
    top = box[0]["players"][0]
    assert top["player"]["name"] and top["minutes"] >= box[0]["players"][-1]["minutes"]


def test_a_live_game_has_a_live_box_score(api, conn):
    go_live(conn, 250)
    box = api.get(f"/api/teams/{KANSAS}/games/{KENTUCKY}").json()["box"]
    assert [b["team"]["name"] for b in box] == ["Kansas", "Kentucky"]
    assert box[0]["totals"]["pts"] < 89  # the score so far
