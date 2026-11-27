"""The game page, as JSON: best and worst lineups, win probability, killshots.

Shared by finished games (the API reads stints and timelines from Postgres) and
live games (`live.py` builds them from ESPN), so both pages are put together
the same way. Everything is turned around to one team's side.
"""
from . import rollup
from .clock import label
from .boxscore import Line, totals
from .events import Run, WinProbPoint
from .stints import Stint

GAME_MIN_POSS = 3  # possessions for a lineup to qualify in a single game


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
        "time_tbd": row["time_tbd"],
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


def killshot(run: Run, team_id: str, is_home: bool) -> dict:
    before, after = ((run.home0, run.away0), (run.home1, run.away1))
    if not is_home:
        before, after = before[::-1], after[::-1]
    return {"by": "team" if run.team_id == team_id else "opponent", "label": f"{run.pts}-0", "pts": run.pts,
            "start": label(run.t0), "end": label(run.t1), "t0": run.t0, "t1": run.t1,
            "score_before": list(before), "score_after": list(after)}


def team_box(team: dict, lines: list[Line], people: dict[str, dict]) -> dict:
    """One team's box score: {team, players, totals}."""
    players = [{**{k: v for k, v in l.as_dict().items() if k != "player_id"}, "player": player(people, l.player_id)}
               for l in lines]
    return {"team": team, "players": players, "totals": totals(lines)}


def build(summary: dict, team_id: str, is_home: bool, stints: list[Stint], win_prob: list[WinProbPoint],
          runs: list[Run], people: dict[str, dict], box: list[dict] | None = None) -> dict:
    """The whole game page for one team. `summary` is the game's row as the games list shows it;
    `box` is the two teams' box scores (from team_box), this team first."""
    best, worst = rollup.best_and_worst(rollup.lineups(stints), min_poss=GAME_MIN_POSS)
    return {"game": summary, "min_poss": GAME_MIN_POSS,
            "lineups": {"best": lineup_rows(best, people), "worst": lineup_rows(worst, people)},
            "win_prob": [w.for_team(is_home) for w in win_prob],
            "killshots": [killshot(r, team_id, is_home) for r in runs],
            "box": box or []}
