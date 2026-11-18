"""Rebuild who was on the floor, from ESPN play-by-play.

ESPN doesn't publish lineups. It does log every substitution, so we start each
game with the five starters and apply each "X subbing in / Y subbing out".

A *stint* is a stretch of game time where one team's five players didn't change.
Every play between substitutions is credited to the stint on the floor, for both
the team and its opponent. Lineup ratings, on/off splits and season totals are
all just sums of stints.

A stint also ends when the game enters or leaves *garbage time* (a margin over
20 in the second half or overtime), even if nobody subbed, so garbage-time play
can be filtered out later without re-reading the game.
"""
from dataclasses import dataclass, field

from .box import Box
from .clock import elapsed, period_length, period_start

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
        """False when substitution data left us with more or fewer than five players."""
        return len(self.player_ids) == 5

    @property
    def lineup_key(self) -> str:
        return ",".join(self.player_ids)


def _team_id(play: dict) -> str | None:
    return (play.get("team") or {}).get("id")


def _actor(play: dict) -> str | None:
    """The primary player in a play (the shooter, the rebounder, the player subbing)."""
    parts = play.get("participants") or []
    return parts[0]["athlete"]["id"] if parts else None


def _infer_period_lineup(plays: list[dict], team_id: str, previous: list[str]) -> list[str]:
    """Who started a period. ESPN doesn't log the five that come out after halftime.

    Anyone who does something (or subs *out*) before subbing *in* during the
    period must have been on the floor at the start. If that finds fewer than
    five, fill in from whoever ended the previous period.
    """
    subbed_in, on = set(), []
    for p in plays:
        if _team_id(p) != team_id:
            continue
        pid = _actor(p)
        if not pid:
            continue
        if p["type"]["text"] == "Substitution":
            if "subbing in" in p["text"]:
                subbed_in.add(pid)
            elif pid not in subbed_in and pid not in on:
                on.append(pid)
        elif pid not in subbed_in and pid not in on:
            on.append(pid)
        if len(on) == 5:
            return on
    for pid in previous:
        if len(on) == 5:
            break
        if pid not in on and pid not in subbed_in:
            on.append(pid)
    return on


def _credit(play: dict, box: Box) -> None:
    """Add one play's counting stats to a Box."""
    text = play["text"].lower()
    kind = play["type"]["text"]
    if play.get("shootingPlay"):
        made = bool(play.get("scoringPlay"))
        if "free throw" in text:
            box.fta += 1
            box.ftm += made
            box.pts += made
        else:
            three = "three point" in text
            box.fga += 1
            box.tpa += three
            if made:
                box.fgm += 1
                box.tpm += three
                box.pts += play.get("scoreValue", 0)
    elif kind == "Offensive Rebound":
        box.oreb += 1
    elif kind == "Defensive Rebound":
        box.dreb += 1
    elif "turnover" in kind.lower():
        box.to += 1


def build_stints(plays: list[dict], team_id: str, starters: list[str], team_is_home: bool,
                 live: bool = False) -> list[Stint]:
    """All stints for one team in one game, in time order.

    `live=True` is for a game in progress: the current period's last stint ends
    at the latest play instead of the end of the period.
    """
    by_period: dict[int, list[dict]] = {}
    for p in plays:
        by_period.setdefault(p["period"]["number"], []).append(p)

    stints: list[Stint] = []
    on = list(starters)
    team_score = opp_score = 0
    current: Stint | None = None

    def close(at: float) -> None:
        nonlocal current
        if current is not None:
            current.t_end = at
            if current.seconds > 0 or current.team.as_dict() != Box().as_dict() or current.opp.as_dict() != Box().as_dict():
                stints.append(current)
        current = None

    last_period = max(by_period) if by_period else 1
    for period in sorted(by_period):
        period_plays = by_period[period]
        if period > 1:
            on = _infer_period_lineup(period_plays, team_id, on)
        t = period_start(period)
        # Open the period's first stint at its opening tip, not at the first logged play.
        garbage = period >= 2 and abs(team_score - opp_score) > GARBAGE_MARGIN
        current = Stint(team_id, tuple(sorted(on)), t, t, garbage)

        for p in period_plays:
            t = elapsed(period, p["clock"]["displayValue"])
            pid, tid = _actor(p), _team_id(p)

            if p["type"]["text"] == "Substitution":
                # Apply now, but don't split yet: subs come in batches at one moment.
                if tid == team_id and pid:
                    if "subbing in" in p["text"]:
                        if pid not in on:
                            on.append(pid)
                    elif pid in on:
                        on.remove(pid)
                continue

            garbage = period >= 2 and abs(team_score - opp_score) > GARBAGE_MARGIN
            key = tuple(sorted(on))
            if current is None or key != current.player_ids or garbage != current.garbage:
                close(t)
                current = Stint(team_id, key, t, t, garbage)

            if tid == team_id:
                _credit(p, current.team)
            elif tid is not None:
                _credit(p, current.opp)

            home, away = p.get("homeScore", 0), p.get("awayScore", 0)
            team_score, opp_score = (home, away) if team_is_home else (away, home)

        if live and period == last_period:
            close(t)  # game in progress: stop at the latest play
        else:
            close(period_start(period) + period_length(period))
    return stints
