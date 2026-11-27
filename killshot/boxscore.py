"""The box score: each player's counting stats for one game, from the plays.

Built the same way from CBBD's plays (finished games) and ESPN's (live games),
so the live box score and the official one agree. Minutes and +/- come from the
stints (who was on the floor), everything else from the plays themselves.
"""
from dataclasses import asdict, dataclass

from . import plays as P
from .stints import Stint


@dataclass
class Line:
    """One player's game. Shooting is made/attempted; reb = oreb + dreb."""
    player_id: str
    minutes: float = 0
    pts: int = 0
    fgm: int = 0
    fga: int = 0
    tpm: int = 0
    tpa: int = 0
    ftm: int = 0
    fta: int = 0
    oreb: int = 0
    dreb: int = 0
    ast: int = 0
    stl: int = 0
    blk: int = 0
    tov: int = 0
    pf: int = 0
    plus_minus: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _credit(line: Line, play: P.Play) -> None:
    """Count one play for the player who made it."""
    if play.kind == P.SHOT:
        line.fga += 1
        line.tpa += play.three
        if play.made:
            line.fgm += 1
            line.tpm += play.three
            line.pts += play.points
    elif play.kind == P.FREE_THROW:
        line.fta += 1
        if play.made:
            line.ftm += 1
            line.pts += play.points
    elif play.kind == P.OFF_REBOUND:
        line.oreb += 1
    elif play.kind == P.DEF_REBOUND:
        line.dreb += 1
    elif play.kind == P.TURNOVER:
        line.tov += 1
    elif play.kind == P.FOUL:
        line.pf += 1
    elif play.kind == P.STEAL:
        line.stl += 1
    elif play.kind == P.BLOCK:
        line.blk += 1


def box_score(plays: list[P.Play], stints: list[Stint], roster: set[str]) -> list[Line]:
    """Every player on one team who played or did something, most minutes first.

    `roster` is that team's player ids. Plays are matched to players, not to the
    play's team, because a steal or a block is logged under whichever team the
    provider chose; the player is the reliable part.
    """
    lines: dict[str, Line] = {}

    def line(pid: str) -> Line:
        return lines.setdefault(pid, Line(pid))

    for s in stints:
        if not s.valid:
            continue
        for pid in s.player_ids:
            line(pid).minutes += s.seconds / 60
            line(pid).plus_minus += s.team.pts - s.opp.pts

    for play in plays:
        if play.player_id in roster and play.kind != P.SUB:
            _credit(line(play.player_id), play)
        if play.assist_id in roster and play.kind == P.SHOT and play.made:
            line(play.assist_id).ast += 1

    for l in lines.values():
        l.minutes = round(l.minutes, 1)
    return sorted(lines.values(), key=lambda l: (-l.minutes, -l.pts))


def totals(lines: list[Line]) -> dict:
    """The team line: every player's stats added up (team rebounds aren't credited to anyone)."""
    keys = [k for k in Line.__dataclass_fields__ if k not in ("player_id", "minutes", "plus_minus")]
    return {k: sum(getattr(l, k) for l in lines) for k in keys}
