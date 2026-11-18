"""Split a game into stints: stretches where one team's five players didn't change.

Our data provider lists the ten players on the floor with every play, so a
stint is simply a run of consecutive plays with the same five for one team.
Every play is credited to the stint on the floor, for both the team and its
opponent. Lineup ratings, on/off splits and season totals are all sums of stints.

A stint also ends when the game enters or leaves *garbage time* (a margin over
20 in the second half or overtime), even if nobody subbed, so garbage-time play
can be filtered out later without re-reading the game.
"""
from dataclasses import dataclass, field

from . import plays as P
from .box import Box
from .clock import period_length, period_start

GARBAGE_MARGIN = 20


@dataclass
class Stint:
    team_id: str
    player_ids: tuple[str, ...]  # sorted, so the same five always produce the same key
    t_start: float
    t_end: float
    garbage: bool
    team: Box = field(default_factory=Box)
    opp: Box = field(default_factory=Box)

    @property
    def seconds(self) -> float:
        return self.t_end - self.t_start

    @property
    def valid(self) -> bool:
        """False when the data didn't list exactly five players for this team."""
        return len(self.player_ids) == 5

    @property
    def lineup_key(self) -> str:
        return ",".join(self.player_ids)


def _credit(play: P.Play, box: Box) -> None:
    """Add one play's counting stats to a Box."""
    if play.kind == P.SHOT:
        box.fga += 1
        box.tpa += play.three
        if play.made:
            box.fgm += 1
            box.tpm += play.three
            box.pts += play.points
    elif play.kind == P.FREE_THROW:
        box.fta += 1
        if play.made:
            box.ftm += 1
            box.pts += play.points
    elif play.kind == P.OFF_REBOUND:
        box.oreb += 1
    elif play.kind == P.DEF_REBOUND:
        box.dreb += 1
    elif play.kind == P.TURNOVER:
        box.to += 1


def build_stints(plays: list[P.Play], team_id: str, team_is_home: bool, live: bool = False) -> list[Stint]:
    """All stints for one team in one game, in time order.

    `live=True` is for a game in progress: the last stint ends at the latest
    play instead of the end of the period.
    """
    stints: list[Stint] = []
    current: Stint | None = None
    team_score = opp_score = 0
    period = None

    def close(at: float) -> None:
        nonlocal current
        if current is not None:
            current.t_end = at
            has_stats = current.team != Box() or current.opp != Box()
            if current.seconds > 0 or has_stats:  # drop the zero-length in-between lineups of a sub batch
                stints.append(current)
        current = None

    for play in plays:
        if play.period != period:  # a new half or overtime starts
            if period is not None:
                close(period_start(period) + period_length(period))
            period = play.period
            garbage = period >= 2 and abs(team_score - opp_score) > GARBAGE_MARGIN
            current = Stint(team_id, play.on_floor.get(team_id, ()), period_start(period), period_start(period), garbage)

        # Lineup and garbage state as of this play. Substitution plays count
        # here too, so the stint changes at the moment of the sub.
        five = play.on_floor.get(team_id, ())
        garbage = period >= 2 and abs(team_score - opp_score) > GARBAGE_MARGIN
        if five != current.player_ids or garbage != current.garbage:
            close(play.t)
            current = Stint(team_id, five, play.t, play.t, garbage)

        if play.team_id == team_id:
            _credit(play, current.team)
        elif play.team_id is not None:
            _credit(play, current.opp)

        team_score, opp_score = (play.home_pts, play.away_pts) if team_is_home else (play.away_pts, play.home_pts)

    if period is not None:
        close(plays[-1].t if live else period_start(period) + period_length(period))
    return stints
