"""The web API: JSON for the frontend, built on the same code as the command line.

    uvicorn killshot.api:app --reload      # then open http://localhost:8000/docs

Every route is read-only and short: it reads from Postgres with `db`, adds
things up with `rollup`, and returns plain JSON. All numbers are from the
requested team's side (its points first, its win probability, its runs vs.
the opponent's).

It also serves the built frontend (web/dist): any path that isn't an API route
gets the React app, which then shows the right page for that URL.

Settings (environment variables): DATABASE_URL, TRACKED_TEAMS (default: Kansas),
WEB_DIST (default: web/dist in this repo).
"""
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse

from . import db, detail, rollup, schemas
from .detail import game_summary, lineup_rows, player
from .events import Run, WinProbPoint

HEALTHY_HEARTBEAT = 30 * 60  # the worker wakes at least every 15 minutes; allow one missed pass

app = FastAPI(title="killshot", description="Lineups, win probability and killshots for college basketball.")


def get_conn() -> Iterator[psycopg.Connection]:
    """One database connection per request, closed afterwards."""
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        yield conn


def tracked(conn: psycopg.Connection) -> dict[str, str]:
    """Team id -> name for the teams this site covers."""
    names = [t.strip() for t in os.environ.get("TRACKED_TEAMS", "Kansas").split(",") if t.strip()]
    return db.team_ids(conn, names)


def require_team(team_id: str, conn: psycopg.Connection) -> str:
    teams = tracked(conn)
    if team_id not in teams:
        raise HTTPException(404, f"team {team_id} isn't tracked")
    return teams[team_id]


# --- routes --------------------------------------------------------------------

@app.get("/healthz")
def healthz(response: Response, conn: psycopg.Connection = Depends(get_conn)) -> schemas.Health:
    """Up if the database answers and the worker has checked in within 30 minutes."""
    age, note = db.worker_heartbeat_age(conn)
    healthy = age is not None and age < HEALTHY_HEARTBEAT
    if not healthy:
        response.status_code = 503
    return {"ok": healthy, "database": "ok", "worker_heartbeat_seconds_ago": age, "worker_note": note}


@app.get("/api/teams")
def teams(conn: psycopg.Connection = Depends(get_conn)) -> list[schemas.Team]:
    return [{"id": i, "name": n} for i, n in tracked(conn).items()]


@app.get("/api/teams/{team_id}/games")
def games(team_id: str, season: int, conn: psycopg.Connection = Depends(get_conn)) -> list[schemas.GameSummary]:
    """The schedule and results for a season, oldest first. A game that is on shows
    its live score and state, from the live page the worker saves every 30 seconds."""
    require_team(team_id, conn)
    live = db.live_games(conn, team_id)
    return [live.get(row["id"]) or game_summary(row, team_id) for row in db.games_for_team(conn, team_id, season)]


@app.get("/api/teams/{team_id}/games/{game_id}")
def game(team_id: str, game_id: str, conn: psycopg.Connection = Depends(get_conn)) -> schemas.GameDetail:
    """One game: best and worst lineups, win probability over time, and killshots.

    While the game is on (and until CBBD's official record arrives after the
    final), this is the live page the worker built from ESPN, with a `live` block."""
    require_team(team_id, conn)
    rows = db.games_for_team(conn, team_id, game_id=game_id)
    if not rows:
        raise HTTPException(404, f"game {game_id} not found for team {team_id}")
    live = db.live_page(conn, game_id, team_id)
    if live:
        page, updated_at = live
        return {**page, "live": {**page["live"], "updated_at": updated_at.isoformat()}}
    row = rows[0]
    home = row["home_team_id"] == team_id
    return detail.build(game_summary(row, team_id), team_id, home,
                        stints=db.stints_for(conn, team_id, game_id=game_id),
                        win_prob=[WinProbPoint(*r) for r in db.win_prob_for_game(conn, game_id)],
                        runs=[Run(*r) for r in db.runs_for_game(conn, game_id)],
                        people=db.players(conn))


@app.get("/api/teams/{team_id}/seasons/{season}")
def season(team_id: str, season: int, min_minutes: float = 20, exclude_garbage: bool = False,
           conn: psycopg.Connection = Depends(get_conn)) -> schemas.Season:
    """Season totals, lineups with at least `min_minutes` together, and on/off splits."""
    name = require_team(team_id, conn)
    stints = db.stints_for(conn, team_id, season=season)
    people = db.players(conn)
    lineups = [r for r in rollup.lineups(stints, exclude_garbage) if r["minutes"] >= min_minutes]
    on_off = []
    for r in rollup.on_off(stints, exclude_garbage):
        on_off.append({**r, "player": player(people, r.pop("player_id"))})
    return {
        "team": {"id": team_id, "name": name}, "season": season, "exclude_garbage": exclude_garbage,
        "totals": rollup.team_totals(stints, exclude_garbage),
        "lineups": sorted(lineup_rows(lineups, people), key=lambda r: -r["net"]),
        "on_off": sorted(on_off, key=lambda r: -r["on_off"]),
    }


# --- the frontend --------------------------------------------------------------
# Registered last, so every API route above matches first.

def web_dist() -> Path:
    return Path(os.environ.get("WEB_DIST", Path(__file__).resolve().parent.parent / "web" / "dist")).resolve()


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    """Serve a built frontend file, or the React app's index.html for any page URL."""
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "no such API route")
    dist = web_dist()
    file = (dist / path).resolve()
    if path and file.is_file() and dist in file.parents:  # never serve anything outside web/dist
        # Vite puts a content hash in asset file names, so they can be cached for good.
        return FileResponse(file, headers={"Cache-Control": "public, max-age=31536000, immutable"}
                            if path.startswith("assets/") else None)
    if path.startswith("assets/"):
        # A missing script must be a 404, not the page: HTML where the browser expects
        # JavaScript leaves a blank screen. (Happens to a tab opened before a rebuild.)
        raise HTTPException(404, "no such file; reload the page")
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(404, "frontend not built: run `npm run build` in web/")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
