"""Our own play format.

Data providers describe plays in their own words ("MadeFreeThrow",
"Lost Ball Turnover", "onFloor"). The translator in `sources/` turns each one
into a `Play`, so the basketball code (stints, events) never sees provider
field names. If the provider changes its format, only the translator changes.
"""
from dataclasses import dataclass, field

# What happened on a play. Anything we don't count (timeouts, steals, blocks,
# jump balls) is "other": steals and blocks are already covered by the
# turnover or missed shot they come with.
SHOT = "shot"              # a field-goal attempt, made or missed
FREE_THROW = "free_throw"
OFF_REBOUND = "oreb"
DEF_REBOUND = "dreb"
TURNOVER = "turnover"
SUB = "sub"
FOUL = "foul"
OTHER = "other"


@dataclass
class Play:
    t: float                 # game seconds elapsed (see clock.py)
    period: int
    team_id: str | None      # the team that made the play; None for e.g. end of period
    kind: str                # one of the constants above
    made: bool = False       # for shots and free throws
    three: bool = False      # for shots
    points: int = 0
    player_id: str | None = None
    sub: str | None = None   # for substitutions: "in" or "out" (player_id is the player)
    home_pts: int = 0        # score after this play
    away_pts: int = 0
    on_floor: dict[str, tuple[str, ...]] = field(default_factory=dict)  # team id -> its five players, sorted
    home_wp: float | None = None  # home team's win probability, 0-100, if the provider has it
