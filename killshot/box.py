"""Counting stats and the ratings built from them.

A `Box` is the handful of counts needed for tempo-free stats. We keep one Box
for each side (the team we're analyzing, and its opponent) for every stint,
then add stints together to rate a lineup, a player's on/off split, or a season.
"""
from dataclasses import dataclass, fields


@dataclass
class Box:
    pts: int = 0
    fga: int = 0   # field-goal attempts (2s and 3s, not free throws)
    fgm: int = 0
    tpa: int = 0   # three-point attempts
    tpm: int = 0
    fta: int = 0   # free-throw attempts
    ftm: int = 0
    oreb: int = 0
    dreb: int = 0
    to: int = 0    # turnovers

    def __add__(self, other: "Box") -> "Box":
        return Box(**{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)})

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# Free throws end a possession less often than shots do (and-ones, technicals, 3-shot
# fouls), so each attempt counts as a fraction of a possession. 0.475 is the usual
# college value; the NBA uses 0.44.
FT_POSSESSION_WEIGHT = 0.475


def possessions(team: Box, opp: Box) -> float:
    """Estimated possessions, averaged over both teams (they should be nearly equal).

    A possession ends with a shot the defense rebounds, a turnover, or free throws,
    so: shots - offensive rebounds + turnovers + weighted free throws.
    """
    def one(b: Box) -> float:
        return b.fga - b.oreb + b.to + FT_POSSESSION_WEIGHT * b.fta
    return (one(team) + one(opp)) / 2


def ratings(team: Box, opp: Box, seconds: float) -> dict | None:
    """Per-100-possession ratings and Four Factors for a stretch of play.

    Returns None when there were no possessions (e.g. a lineup that only
    checked in for a dead-ball free throw).
    """
    poss = possessions(team, opp)
    if poss <= 0:
        return None

    def pct(num, den):
        return round(num / den, 3) if den else None

    ortg = 100 * team.pts / poss
    drtg = 100 * opp.pts / poss
    return {
        "minutes": round(seconds / 60, 1),
        "poss": round(poss, 1),
        "pts": team.pts,
        "opp_pts": opp.pts,
        "plus_minus": team.pts - opp.pts,
        "ortg": round(ortg, 1),            # points scored per 100 possessions
        "drtg": round(drtg, 1),            # points allowed per 100 possessions
        "net": round(ortg - drtg, 1),
        "efg": pct(team.fgm + 0.5 * team.tpm, team.fga),     # a made 3 counts as 1.5 makes
        "opp_efg": pct(opp.fgm + 0.5 * opp.tpm, opp.fga),
        "tov": pct(team.to, poss),                            # turnovers per possession
        "orb": pct(team.oreb, team.oreb + opp.dreb),          # share of own misses rebounded
        "ftr": pct(team.fta, team.fga),                       # free-throw attempts per shot
    }
