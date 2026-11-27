"""ESPN: fetching a game's summary, and translating it into our own format.

Used only for the live view. CBBD has no live play-by-play for basketball, so
during a game we read ESPN's (free, unofficial) summary instead. Nothing from
here is saved as history: after the final, CBBD's record replaces it.

This is the only file that knows ESPN's URLs and field names. ESPN's plays look
a lot like CBBD's (CBBD's data appears to start from ESPN's), with one big gap:
ESPN never says who is on the floor, so `fill_lineups` works it out from
substitutions.

ESPN's ids are not CBBD's: team and player ids here are ESPN's own, and stay
inside the live view.
"""
import json
import time
import urllib.error
import urllib.request

from .. import plays as P
from ..clock import elapsed
from ..game import Game, Player, Team
from ..substitutions import fill_lineups

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
USER_AGENT = "killshot/0.2 (basketball analytics)"


def summary(event_id: str, tries: int = 3) -> dict:
    """ESPN's summary of one game: header, box score, plays, win probability (one call).
    Retries network errors with backoff (1s, 2s)."""
    url = f"{BASE}/summary?event={event_id}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


# --- translation -------------------------------------------------------------

def play_kind(p: dict) -> str:
    """ESPN's play type -> our play kind. Same names as CBBD's, so the same rules."""
    kind = p["type"]["text"]
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
    if kind == "Steal":
        return P.STEAL
    if kind == "Block Shot":
        return P.BLOCK
    return P.OTHER


def to_play(p: dict, home_wp: dict[str, float]) -> P.Play:
    """One ESPN play -> our Play. `home_wp` maps play id -> home win probability (0-1)."""
    kind = play_kind(p)
    text = (p.get("text") or "").lower()
    sub = None
    if kind == P.SUB:
        sub = "in" if "subbing in" in text else "out" if "subbing out" in text else None
    participants = p.get("participants") or []
    wp = home_wp.get(p["id"])
    return P.Play(
        t=elapsed(p["period"]["number"], p["clock"]["displayValue"]),
        period=p["period"]["number"],
        team_id=(p.get("team") or {}).get("id"),
        kind=kind,
        # like CBBD, ESPN labels missed free throws "MadeFreeThrow"; scoringPlay is right
        made=bool(p.get("scoringPlay")),
        three=p.get("pointsAttempted") == 3,
        points=int(p.get("scoreValue") or 0) if p.get("scoringPlay") else 0,
        # ESPN lists the shooter first and the assister second
        player_id=participants[0]["athlete"]["id"] if participants else None,
        assist_id=participants[1]["athlete"]["id"] if len(participants) > 1 and "assist" in text else None,
        sub=sub,
        home_pts=p["homeScore"],
        away_pts=p["awayScore"],
        home_wp=100 * wp if wp is not None else None,
    )


def to_game(data: dict) -> Game:
    """An ESPN summary -> a fully analyzed Game, with ESPN's ids."""
    comp = data["header"]["competitions"][0]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    home, away = (Team(sides[s]["team"]["id"], sides[s]["team"]["location"], s == "home",
                       int(sides[s].get("score") or 0)) for s in ("home", "away"))
    status = comp["status"]["type"]
    game = Game(id=data["header"]["id"], espn_id=data["header"]["id"],
                season=data["header"]["season"]["year"], start=comp["date"],
                state=status["state"], status=status["shortDetail"],
                neutral_site=bool(comp.get("neutralSite")), home=home, away=away)

    for team in data.get("boxscore", {}).get("players", []):
        for group in team["statistics"]:
            for a in group["athletes"]:
                person = a["athlete"]
                game.players[person["id"]] = Player(person["id"], team["team"]["id"], person["displayName"])

    home_wp = {w["playId"]: w["homeWinPercentage"] for w in data.get("winprobability") or []}
    plays = [to_play(p, home_wp) for p in data.get("plays") or []]
    game.lineups_filled = fill_lineups(plays, [home.id, away.id])
    game.analyze(plays)
    return game
