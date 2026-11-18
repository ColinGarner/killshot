"""The web API: JSON for the frontend, built on the same code as the command line.

    uvicorn killshot.api:app --reload      # then open http://localhost:8000/docs

Every route is read-only and short: it reads from Postgres with `db`, adds
things up with `rollup`, and returns plain JSON. All numbers are from the
requested team's side (its points first, its win probability, its runs vs.
the opponent's).

Settings (environment variables): DATABASE_URL, TRACKED_TEAMS (default: Kansas).
"""
import os
from collections.abc import Iterator

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response

from . import db, rollup
from .clock import label
from .events import WinProbPoint

HEALTHY_HEARTBEAT = 30 * 60  # the worker wakes at least every 15 minutes; allow one missed pass
GAME_MIN_POSS = 3            # possessions for a lineup to qualify in a single game

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


def game_summary(row: dict, team_id: str) -> dict:
    """One games-table row, turned around to the requested team's side."""
    home = row["home_team_id"] == team_id
    pts, opp_pts = (row["home_pts"], row["away_pts"]) if home else (row["away_pts"], row["home_pts"])
    if row["state"] == "pre":
        pts = opp_pts = None  # CBBD sends 0-0 for games not yet played
    final = row["state"] == "post" and pts is not None and opp_pts is not None
    return {
        "id": row["id"],
        "start_at": row["start_at"].isoformat(),
        "state": row["state"],                  # "pre", "in" or "post"
        "status": row["status"],
        "venue": "neutral" if row["neutral_site"] else ("home" if home else "away"),
        "opponent": {"id": row["away_team_id"] if home else row["home_team_id"],
                     "name": row["away_name"] if home else row["home_name"]},
        "pts": pts,
        "opp_pts": opp_pts,
        "result": ("W" if pts > opp_pts else "L") if final else None,
        "has_plays": row["has_plays"],          # False until CBBD publishes play-by-play after the final
    }


def player(people: dict[str, dict], player_id: str) -> dict:
    return people.get(player_id, {"id": player_id, "name": player_id, "short_name": player_id})


def lineup_rows(rows: list[dict], people: dict[str, dict]) -> list[dict]:
    """Replace player ids with {id, name, short_name}, for display."""
    return [{**r, "players": [player(people, p) for p in r.pop("player_ids")]} for r in rows]


# --- routes --------------------------------------------------------------------

@app.get("/healthz")
def healthz(response: Response, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    """Up if the database answers and the worker has checked in within 30 minutes."""
    age, note = db.worker_heartbeat_age(conn)
    healthy = age is not None and age < HEALTHY_HEARTBEAT
    if not healthy:
        response.status_code = 503
    return {"ok": healthy, "database": "ok", "worker_heartbeat_seconds_ago": age, "worker_note": note}


@app.get("/api/teams")
def teams(conn: psycopg.Connection = Depends(get_conn)) -> list[dict]:
    return [{"id": i, "name": n} for i, n in tracked(conn).items()]


@app.get("/api/teams/{team_id}/games")
def games(team_id: str, season: int, conn: psycopg.Connection = Depends(get_conn)) -> list[dict]:
    """The schedule and results for a season, oldest first."""
    require_team(team_id, conn)
    return [game_summary(row, team_id) for row in db.games_for_team(conn, team_id, season)]


@app.get("/api/teams/{team_id}/games/{game_id}")
def game(team_id: str, game_id: str, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    """One game: best and worst lineups, win probability over time, and killshots."""
    require_team(team_id, conn)
    rows = db.games_for_team(conn, team_id, game_id=game_id)
    if not rows:
        raise HTTPException(404, f"game {game_id} not found for team {team_id}")
    row = rows[0]
    summary = game_summary(row, team_id)
    home = row["home_team_id"] == team_id
    people = db.players(conn)

    best, worst = rollup.best_and_worst(rollup.lineups(db.stints_for(conn, team_id, game_id=game_id)),
                                        min_poss=GAME_MIN_POSS)
    win_prob = [WinProbPoint(*r).for_team(home) for r in db.win_prob_for_game(conn, game_id)]

    killshots = []
    for team, pts, t0, t1, home0, away0, home1, away1 in db.runs_for_game(conn, game_id):
        before, after = ((home0, away0), (home1, away1)) if home else ((away0, home0), (away1, home1))
        killshots.append({"by": "team" if team == team_id else "opponent", "label": f"{pts}-0", "pts": pts,
                          "start": label(t0), "end": label(t1), "t0": t0, "t1": t1,
                          "score_before": list(before), "score_after": list(after)})

    return {"game": summary, "min_poss": GAME_MIN_POSS,
            "lineups": {"best": lineup_rows(best, people), "worst": lineup_rows(worst, people)},
            "win_prob": win_prob, "killshots": killshots}


@app.get("/api/teams/{team_id}/seasons/{season}")
def season(team_id: str, season: int, min_minutes: float = 20, exclude_garbage: bool = False,
           conn: psycopg.Connection = Depends(get_conn)) -> dict:
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

