"""CollegeBasketballData.com: fetching, and translating into our own format.

This is the only file that knows CBBD's URLs and field names. If CBBD changes
its API, this is the file to fix.

Authentication: CBBD wants `Authorization: Bearer <key>`. We send the key from
the CBBD_API_KEY environment variable when it's set. (In the Claude Code
environment the network proxy adds the key instead, so the variable can be unset.)
"""
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Callable

from .. import plays as P
from ..clock import period_length, period_start
from ..game import Game, Player, Team
from ..substitutions import fill_lineups

BASE = "https://api.collegebasketballdata.com"
USER_AGENT = "killshot/0.2 (basketball analytics)"

# CBBD game status -> our three states
STATES = {"scheduled": "pre", "in_progress": "in", "final": "post",
          "postponed": "pre", "cancelled": "post"}


class Client:
    """Makes CBBD requests. `on_call` runs once per request, so the caller can
    count API usage against the monthly limit (see db.count_api_call)."""

    def __init__(self, on_call: Callable[[], None] | None = None):
        self.on_call = on_call

    def get(self, path: str, tries: int = 4, **params) -> list | dict:
        """GET a JSON document, retrying with backoff (1s, 2s, 4s) on network errors."""
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{BASE}{path}" + (f"?{query}" if query else "")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if os.environ.get("CBBD_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['CBBD_API_KEY']}"
        for attempt in range(tries):
            if self.on_call:
                self.on_call()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404) or attempt == tries - 1:
                    raise  # retrying won't fix a bad key or a missing game
            except OSError:
                if attempt == tries - 1:
                    raise
            time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def games(self, team: str, season: int) -> list[dict]:
        """A team's games for a season (one call). `team` is CBBD's name, e.g. 'Kansas'."""
        return self.get("/games", team=team, season=season)

    def plays(self, game_id: str) -> list[dict]:
        """Every play of one game, with the ten players on the floor (one call)."""
        return self.get(f"/plays/game/{game_id}")

    def game_data(self, game: dict) -> dict:
        """Everything we store for one game: CBBD's game record plus its plays."""
        return {"game": game, "plays": self.plays(game["id"])}


# --- translation -------------------------------------------------------------

def play_kind(p: dict) -> str:
    """CBBD's playType -> our play kind."""
    kind = p["playType"]
    if p.get("shootingPlay"):
        return P.FREE_THROW if "FreeThrow" in kind else P.SHOT
    if kind == "Offensive Rebound":
        return P.OFF_REBOUND
    if kind == "Defensive Rebound":
        return P.DEF_REBOUND
    if "Turnover" in kind:
        return P.TURNOVER
    if kind == "Substitution":
        return P.SUB
    if "Foul" in kind:
        return P.FOUL
    return P.OTHER


def to_play(p: dict, team_ids: dict[str, str]) -> P.Play:
    """One CBBD play -> our Play. `team_ids` maps CBBD team names to ids (onFloor only has names)."""
    shot = p.get("shotInfo") or {}
    on_floor: dict[str, list[str]] = {}
    for player in p.get("onFloor") or []:
        on_floor.setdefault(team_ids[player["team"]], []).append(str(player["id"]))
    participants = p.get("participants") or []
    wp = p.get("homeWinProbability")
    text = (p.get("playText") or "").lower()
    kind = play_kind(p)
    sub = None
    if kind == P.SUB:
        sub = "in" if "subbing in" in text else "out" if "subbing out" in text else None
    return P.Play(
        # secondsRemaining counts down within the period; we count up from tip-off
        t=period_start(p["period"]) + period_length(p["period"]) - p["secondsRemaining"],
        period=p["period"],
        team_id=str(p["teamId"]) if p.get("teamId") is not None else None,
        kind=kind,
        # CBBD labels every free throw "MadeFreeThrow", even misses, so trust scoringPlay
        made=bool(p.get("scoringPlay")),
        three=shot.get("range") == "three_pointer",
        points=int(p.get("scoreValue") or 0),
        player_id=str(participants[0]["id"]) if participants else None,
        sub=sub,
        home_pts=p["homeScore"],
        away_pts=p["awayScore"],
        on_floor={tid: tuple(sorted(ids)) for tid, ids in on_floor.items()},
        home_wp=100 * wp if wp is not None else None,
    )


def to_game(data: dict) -> Game:
    """CBBD's game record + plays (as returned by `Client.game_data`) -> a fully analyzed Game."""
    g, raw_plays = data["game"], data.get("plays") or []
    home = Team(str(g["homeTeamId"]), g["homeTeam"], True, g.get("homePoints") or 0)
    away = Team(str(g["awayTeamId"]), g["awayTeam"], False, g.get("awayPoints") or 0)
    state = STATES.get(g["status"], "pre")
    game = Game(id=str(g["id"]), espn_id=g.get("sourceId"), season=g["season"], start=g["startDate"],
                state=state, status=g["status"].replace("_", " ").title(),
                neutral_site=bool(g.get("neutralSite")), home=home, away=away)

    team_ids = {g["homeTeam"]: home.id, g["awayTeam"]: away.id}
    plays = [to_play(p, team_ids) for p in raw_plays]
    # Some games list incomplete lineups (see substitutions.py); fill them from subs.
    game.lineups_filled = fill_lineups(plays, [home.id, away.id])
    for p in raw_plays:
        for person in p.get("onFloor") or []:
            pid = str(person["id"])
            if pid not in game.players:
                game.players[pid] = Player(pid, team_ids[person["team"]], person["name"])
    game.analyze(plays)
    return game
