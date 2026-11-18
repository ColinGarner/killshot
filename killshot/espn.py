"""The only module that talks to ESPN.

ESPN's site API is public but undocumented, so every URL lives here. If ESPN
changes something, this is the file to fix.
"""
import json
import time
import urllib.request

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
USER_AGENT = "killshot/0.1 (basketball analytics)"


def get(url: str, tries: int = 4, timeout: float = 30) -> dict:
    """GET a JSON document, retrying with backoff (1s, 2s, 4s) on network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def summary(event_id: str) -> dict:
    """Everything about one game: box score, every play, win probability."""
    return get(f"{BASE}/summary?event={event_id}")


def schedule(team_id: str, season: int, season_type: int = 2) -> dict:
    """A team's games for a season. `season` is the year it ends (2027 = 2026-27).

    season_type 2 is the regular season, 3 the postseason.
    """
    return get(f"{BASE}/teams/{team_id}/schedule?season={season}&seasontype={season_type}")
