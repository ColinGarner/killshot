"""The shapes of the API's JSON responses.

Each class is one JSON object: its fields and their types. FastAPI checks every
response against these, shows them on /docs, and publishes them as an OpenAPI
schema, from which the frontend's TypeScript types are generated
(`npm run gen:api` in web/). Change a field here and the frontend's type check
points at every place that needs updating.
"""
from typing import Literal

from pydantic import BaseModel


class Team(BaseModel):
    id: str
    name: str


class Player(BaseModel):
    id: str
    name: str          # "Leroy Blyden Jr."
    short_name: str    # "Blyden", for lineup labels


class Ratings(BaseModel):
    """Tempo-free numbers for a stretch of play (see killshot/box.py)."""
    minutes: float
    poss: float
    pts: int
    opp_pts: int
    plus_minus: int
    ortg: float            # points scored per 100 possessions
    drtg: float            # points allowed per 100 possessions
    net: float             # ortg - drtg
    efg: float | None      # effective field-goal %, as a fraction
    opp_efg: float | None
    tov: float | None      # turnovers per possession
    orb: float | None      # offensive rebound rate
    ftr: float | None      # free-throw attempts per shot


class Lineup(Ratings):
    players: list[Player]
    stints: int            # separate stretches this five played together


class GameSummary(BaseModel):
    id: str
    start_at: str          # ISO time, UTC
    time_tbd: bool         # the date is set but the tip time isn't announced yet
    state: Literal["pre", "in", "post"]
    status: str
    venue: Literal["home", "away", "neutral"]
    opponent: Team
    pts: int | None        # this team's points; None before the game
    opp_pts: int | None
    result: Literal["W", "L"] | None
    has_plays: bool        # False until CBBD publishes play-by-play after the final
    live: bool = False     # the score and state are from ESPN's live feed (see GameDetail.live)


class WinProbPoint(BaseModel):
    t: int                 # game seconds elapsed: 0 at tip, 1200 at half, 2400 end of regulation
    clock: str             # "2nd 18:35"
    win_prob: float        # this team's chance of winning, 0-100
    pts: int
    opp_pts: int


class Killshot(BaseModel):
    by: Literal["team", "opponent"]
    label: str             # "12-0"
    pts: int
    start: str             # clock at the start of the run
    end: str
    t0: int
    t1: int
    score_before: list[int]  # [this team, opponent]
    score_after: list[int]


class GameLineups(BaseModel):
    best: list[Lineup]
    worst: list[Lineup]


class Live(BaseModel):
    """Only while a game is on (and until CBBD's official record replaces it after the final)."""
    updated_at: str        # ISO time, UTC, when the worker last read ESPN
    clock: str | None      # "2nd 12:41"; None before the first play
    on_floor: list[Player] # this team's five right now


class GameDetail(BaseModel):
    game: GameSummary
    min_poss: int          # possessions a lineup needs to be listed
    lineups: GameLineups
    win_prob: list[WinProbPoint]
    killshots: list[Killshot]
    live: Live | None = None  # set while the page is built from ESPN's live feed


class OnOff(BaseModel):
    player: Player
    on: Ratings
    off: Ratings | None
    on_off: float          # team net rating with him on, minus off


class Season(BaseModel):
    team: Team
    season: int
    exclude_garbage: bool
    totals: Ratings | None
    lineups: list[Lineup]
    on_off: list[OnOff]


class Health(BaseModel):
    ok: bool
    database: str
    worker_heartbeat_seconds_ago: float | None
    worker_note: str | None


class VapidKey(BaseModel):
    public_key: str | None   # None if the server has no VAPID_PUBLIC_KEY configured


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    """What the browser's PushManager.subscribe() hands back, reshaped for the API."""
    endpoint: str
    keys: PushSubscriptionKeys


class PushUnsubscribe(BaseModel):
    endpoint: str


class Ok(BaseModel):
    ok: bool = True
