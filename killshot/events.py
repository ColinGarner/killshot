"""Win probability and killshots: the two game timelines.

Both are stored from the *home* team's side, so one stored game serves either
team. `for_team()` flips them when a page asks for one team's view.
"""
from dataclasses import dataclass

from . import clock

KILLSHOT_MIN = 10  # a killshot is a run of 10+ unanswered points


@dataclass
class WinProbPoint:
    t: int            # game seconds elapsed
    home_wp: float    # home team's win probability, 0-100
    home_pts: int
    away_pts: int

    def for_team(self, is_home: bool) -> dict:
        return {
            "t": self.t, "clock": clock.label(self.t),
            "win_prob": self.home_wp if is_home else round(100 - self.home_wp, 1),
            "pts": self.home_pts if is_home else self.away_pts,
            "opp_pts": self.away_pts if is_home else self.home_pts,
        }


@dataclass
class Run:
    team_id: str      # the team on the run
    pts: int          # 12 means a 12-0 run
    t0: int           # starts at the other team's last score
    t1: int           # ends at this team's last score of the run
    home0: int
    away0: int
    home1: int
    away1: int

    @property
    def label(self) -> str:
        return f"{self.pts}-0"


def win_probability(summary: dict, plays: list[dict], every: int = 10) -> list[WinProbPoint]:
    """ESPN's play-by-play win probability, thinned to about one point per 10 game seconds.

    ESPN gives a probability per play id; we look up each play's time and score.
    """
    by_id = {p["id"]: p for p in plays}
    raw = summary.get("winprobability") or []
    points: list[WinProbPoint] = []
    last_t = -every
    for i, w in enumerate(raw):
        p = by_id.get(w.get("playId"))
        if p is None:
            continue
        t = round(clock.elapsed(p["period"]["number"], p["clock"]["displayValue"]))
        is_last = i == len(raw) - 1
        if t - last_t < every and not is_last:
            continue
        last_t = t
        points.append(WinProbPoint(t, round(100 * w["homeWinPercentage"], 1),
                                   p.get("homeScore", 0), p.get("awayScore", 0)))
    return points


def killshots(plays: list[dict], minimum: int = KILLSHOT_MIN) -> list[Run]:
    """Every scoring run of `minimum`+ unanswered points, by either team.

    Walk the scoring plays in order. Consecutive scores by the same team extend
    a run; a score by the other team ends it.
    """
    runs: list[Run] = []
    current: dict | None = None
    home = away = 0  # score before the current scoring play

    def finish():
        if current and current["pts"] >= minimum:
            runs.append(Run(**current))

    for p in plays:
        if not p.get("scoringPlay") or not p.get("team"):
            continue
        team = p["team"]["id"]
        t = round(clock.elapsed(p["period"]["number"], p["clock"]["displayValue"]))
        if current is None or team != current["team_id"]:
            finish()
            start = current["t1"] if current else 0
            current = dict(team_id=team, pts=0, t0=start, t1=t, home0=home, away0=away, home1=home, away1=away)
        current["pts"] += p.get("scoreValue", 0)
        home, away = p["homeScore"], p["awayScore"]
        current.update(t1=t, home1=home, away1=away)
    finish()
    return runs
