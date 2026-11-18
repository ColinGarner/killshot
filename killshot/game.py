"""Turn one ESPN game summary into everything killshot knows about the game.

`Game.from_summary()` is the single entry point: give it ESPN's JSON for a game
(finished or in progress) and get back both teams, players, stints for both
sides, win probability, killshots, and a data-quality check.
"""
from dataclasses import dataclass, field

from . import events
from .stints import Stint, build_stints

SUFFIXES = {"Jr", "Jr.", "Sr", "Sr.", "II", "III", "IV"}


def short_name(full: str) -> str:
    """'Dennis Parker Jr.' -> 'Parker', 'Trey Kaufman-Renn' -> 'Kaufman-Renn'."""
    parts = full.split()
    if len(parts) > 2 and parts[-1] in SUFFIXES:
        return parts[-2]
    return parts[-1]


@dataclass
class Team:
    id: str
    name: str
    abbr: str
    color: str | None
    is_home: bool
    score: int


@dataclass
class Player:
    id: str
    team_id: str
    name: str
    position: str
    starter: bool
    minutes: int   # from ESPN's box score, used to check our reconstruction
    pts: int

    @property
    def short_name(self) -> str:
        return short_name(self.name)


@dataclass
class Game:
    id: str
    season: int              # year the season ends: 2027 = 2026-27
    start: str               # ISO time from ESPN, UTC
    state: str               # "pre", "in" or "post"
    status: str              # ESPN's short status, e.g. "Final" or "12:41 - 2nd"
    neutral_site: bool
    home: Team
    away: Team
    players: dict[str, Player] = field(default_factory=dict)
    stints: dict[str, list[Stint]] = field(default_factory=dict)  # by team id
    win_prob: list[events.WinProbPoint] = field(default_factory=list)
    runs: list[events.Run] = field(default_factory=list)

    def team(self, team_id: str) -> Team:
        return self.home if self.home.id == team_id else self.away

    def opponent(self, team_id: str) -> Team:
        return self.away if self.home.id == team_id else self.home

    def quality(self, team_id: str) -> dict:
        """How well our reconstruction matches ESPN's box score for one team.

        `points_match`: stint points add up to the final score for both sides.
        `max_minutes_error`: worst gap between a player's rebuilt minutes and the box score.
        """
        valid = [s for s in self.stints.get(team_id, []) if s.valid]
        rebuilt: dict[str, float] = {}
        for s in valid:
            for pid in s.player_ids:
                rebuilt[pid] = rebuilt.get(pid, 0) + s.seconds / 60
        mine = [p for p in self.players.values() if p.team_id == team_id]
        worst = max((abs(rebuilt.get(p.id, 0) - p.minutes) for p in mine), default=0)
        pts = sum(s.team.pts for s in valid), sum(s.opp.pts for s in valid)
        return {
            "points_match": pts == (self.team(team_id).score, self.opponent(team_id).score),
            "rebuilt_points": pts,
            "max_minutes_error": round(worst, 1),
            "invalid_seconds": round(sum(s.seconds for s in self.stints.get(team_id, []) if not s.valid)),
        }

    @classmethod
    def from_summary(cls, summary: dict, live: bool | None = None) -> "Game":
        comp = summary["header"]["competitions"][0]
        status = comp["status"]["type"]
        state = status["state"]
        if live is None:
            live = state == "in"

        teams = {}
        for c in comp["competitors"]:
            t = c["team"]
            teams[c["homeAway"]] = Team(
                id=t["id"], name=t.get("displayName") or t.get("location", ""),
                abbr=t.get("abbreviation", ""), color=t.get("color"),
                is_home=c["homeAway"] == "home", score=int(c.get("score") or 0))

        game = cls(id=summary["header"]["id"], season=summary["header"]["season"]["year"],
                   start=comp["date"], state=state,
                   status=status.get("shortDetail") or status.get("detail", ""),
                   neutral_site=bool(comp.get("neutralSite")), home=teams["home"], away=teams["away"])

        for group in (summary.get("boxscore") or {}).get("players", []):
            team_id = group["team"]["id"]
            for a in group["statistics"][0]["athletes"]:
                stats = dict(zip(group["statistics"][0]["names"], a.get("stats") or []))
                game.players[a["athlete"]["id"]] = Player(
                    id=a["athlete"]["id"], team_id=team_id, name=a["athlete"]["displayName"],
                    position=(a["athlete"].get("position") or {}).get("abbreviation", ""),
                    starter=bool(a.get("starter")),
                    minutes=_int(stats.get("MIN")), pts=_int(stats.get("PTS")))

        plays = summary.get("plays") or []
        for team in (game.home, game.away):
            starters = [p.id for p in game.players.values() if p.team_id == team.id and p.starter]
            game.stints[team.id] = build_stints(plays, team.id, starters, team.is_home, live=live)
        game.win_prob = events.win_probability(summary, plays)
        game.runs = events.killshots(plays)
        return game


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0  # ESPN uses "--" for players who didn't play
