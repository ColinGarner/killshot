"""Everything killshot knows about one game, in our own terms.

A data source (see `sources/`) builds a `Game` from its own format; from here
on nothing depends on where the data came from.
"""
from dataclasses import dataclass, field

from . import events
from .plays import Play
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
    is_home: bool
    score: int


@dataclass
class Player:
    id: str
    team_id: str
    name: str

    @property
    def short_name(self) -> str:
        return short_name(self.name)


@dataclass
class Game:
    id: str
    espn_id: str | None      # the same game's ESPN event id, handy for cross-checking
    season: int              # year the season ends: 2027 = 2026-27
    start: str               # ISO time, UTC
    state: str               # "pre", "in" or "post"
    status: str              # short human status, e.g. "Final" or "2nd 12:41"
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

    def analyze(self, plays: list[Play]) -> None:
        """Fill in stints for both teams, win probability and killshots from the plays."""
        live = self.state == "in"
        for team in (self.home, self.away):
            self.stints[team.id] = build_stints(plays, team.id, team.is_home, live=live)
        self.win_prob = events.win_probability(plays)
        self.runs = events.killshots(plays)

    def quality(self, team_id: str) -> dict:
        """Does the reconstruction hold together for one team?

        `points_match`: stint points add up to the final score for both sides.
        `invalid_seconds`: time where the data didn't list exactly five players.
        `has_win_prob`: the provider included win probability for this game.
        """
        stints = self.stints.get(team_id, [])
        valid = [s for s in stints if s.valid]
        pts = sum(s.team.pts for s in valid), sum(s.opp.pts for s in valid)
        return {
            "points_match": pts == (self.team(team_id).score, self.opponent(team_id).score),
            "rebuilt_points": pts,
            "invalid_seconds": round(sum(s.seconds for s in stints if not s.valid)),
            "has_win_prob": bool(self.win_prob),
        }

    def minutes(self, team_id: str) -> dict[str, float]:
        """Minutes played per player, from the stints."""
        out: dict[str, float] = {}
        for s in self.stints.get(team_id, []):
            if s.valid:
                for pid in s.player_ids:
                    out[pid] = out.get(pid, 0) + s.seconds / 60
        return out
