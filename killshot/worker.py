"""The worker: keeps the database up to date with nobody running commands.

    python -m killshot.worker          # run forever (what Railway will run)
    python -m killshot.worker --once   # one pass, then exit (handy for testing)

Each pass of the loop:
1. Refreshes each tracked team's schedule from CBBD (every 10 minutes around a
   game, every 6 hours otherwise), so new games, tip times and finals show up.
2. Fetches plays for any finished game we don't have plays for yet, and saves
   the game. CBBD publishes plays some time after the final, so an empty answer
   is retried after 5, 10, 20, 40, then every 60 minutes.
3. Records a heartbeat, so a health check can tell the worker is alive.

It never spends more than the monthly CBBD allowance: at 90% it slows down 4x,
and at 100% it stops calling until the next month.

Settings (environment variables):
    DATABASE_URL         Postgres connection string (required)
    TRACKED_TEAMS        comma-separated CBBD team names (default: Kansas)
    CBBD_MONTHLY_LIMIT   API calls allowed per month (default: 5000, Tier 1)
    CBBD_API_KEY         CBBD key (in Claude Code the network proxy adds it instead)
"""
import argparse
import datetime as dt
import os
import signal
import time
from dataclasses import dataclass

from . import db
from .sources import cbbd

GAME_DAY_SYNC = 10 * 60        # seconds between schedule syncs around a game
IDLE_SYNC = 6 * 60 * 60        # ... and the rest of the time
GAME_WINDOW_BEFORE = 1         # hours before tip-off that count as "around a game"
GAME_WINDOW_AFTER = 4          # hours after tip-off (covers overtime and a slow final)
PLAYS_RETRY_MINUTES = [5, 10, 20, 40, 60]   # waits after each empty plays answer; then 60 forever
MAX_PLAYS_CHECKS = 48          # about two days of hourly tries, then give up and flag it
SLOW_DOWN_AT = 0.9             # share of the monthly limit where polling slows down
MAX_SLEEP = 15 * 60            # longest wait between passes, so the heartbeat stays fresh


@dataclass
class Settings:
    teams: list[str]
    monthly_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        teams = [t.strip() for t in os.environ.get("TRACKED_TEAMS", "Kansas").split(",") if t.strip()]
        return cls(teams=teams, monthly_limit=int(os.environ.get("CBBD_MONTHLY_LIMIT", "5000")))


def log(message: str) -> None:
    """One timestamped line on stdout. On Railway this becomes the service log."""
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S}Z  {message}", flush=True)


def current_season(today: dt.date) -> int:
    """College seasons are named for the year they end: November 2026 is season 2027."""
    return today.year + 1 if today.month >= 8 else today.year


def budget_multiplier(calls_used: int, limit: int) -> float | None:
    """How much to stretch every wait, given this month's API usage.
    None means the allowance is used up: make no calls."""
    if calls_used >= limit:
        return None
    if calls_used >= SLOW_DOWN_AT * limit:
        return 4.0
    return 1.0


def is_placeholder(record: dict) -> bool:
    """CBBD lists an unknown opponent as a team literally named 'TBD'."""
    return "TBD" in (record.get("homeTeam"), record.get("awayTeam"))


def sync_schedules(conn, client: cbbd.Client, settings: Settings, season: int) -> int:
    """Refresh every tracked team's games for the season. Returns how many games were stored."""
    stored = 0
    for team in settings.teams:
        for record in client.games(team, season):
            if is_placeholder(record):
                continue  # picked up once the opponent is known
            db.upsert_scheduled_game(conn, record, cbbd.STATES.get(record["status"], "pre"))
            stored += 1
    return stored


def fetch_finished_games(conn, client: cbbd.Client) -> list[str]:
    """Fetch and save plays for finished games that don't have them yet.
    Returns a log line for each game handled."""
    notes = []
    for game_id, record in db.games_needing_plays(conn, MAX_PLAYS_CHECKS):
        data = {"game": record, "plays": client.plays(game_id)}
        name = f"{record['awayTeam']} @ {record['homeTeam']}"
        if not data["plays"]:
            tries = db.plays_checks(conn, game_id)
            wait = PLAYS_RETRY_MINUTES[min(tries, len(PLAYS_RETRY_MINUTES) - 1)]
            tries = db.plays_not_ready(conn, game_id, wait)
            gave_up = " Giving up; check this game by hand." if tries >= MAX_PLAYS_CHECKS else ""
            notes.append(f"{name}: final, but CBBD has no plays yet (try {tries}); next try in {wait} min.{gave_up}")
            continue
        game = cbbd.to_game(data)
        db.save_game(conn, game, data)
        q = [game.quality(t.id) for t in (game.home, game.away)]
        ok = all(x["points_match"] and x["invalid_seconds"] == 0 for x in q)
        notes.append(f"{name} {game.away.score}-{game.home.score}: saved {len(data['plays'])} plays"
                     + ("" if ok else "  <- reconstruction doesn't add up, check it"))
    return notes


def run_once(conn, client: cbbd.Client, settings: Settings, today: dt.date) -> float:
    """One pass of the loop. Returns how many seconds to wait before the next."""
    stretch = budget_multiplier(db.api_calls_this_month(conn), settings.monthly_limit)
    if stretch is None:
        db.heartbeat(conn, "monthly CBBD limit reached; not calling until next month")
        log("monthly CBBD limit reached; sleeping an hour")
        return 3600

    near_game = db.game_near(conn, settings.teams, GAME_WINDOW_BEFORE, GAME_WINDOW_AFTER)
    sync_every = (GAME_DAY_SYNC if near_game else IDLE_SYNC) * stretch
    since = db.seconds_since_schedule_sync(conn)
    synced = since is None or since >= sync_every
    if synced:
        stored = sync_schedules(conn, client, settings, current_season(today))
        log(f"schedule synced for {', '.join(settings.teams)}: {stored} games")

    notes = fetch_finished_games(conn, client)
    for note in notes:
        log(note)

    calls = db.api_calls_this_month(conn)
    db.heartbeat(conn, f"ok; {calls} CBBD calls this month", synced_schedule=synced)
    # Wake up for the next schedule sync, or sooner if a finished game is waiting on plays.
    wait = sync_every if synced else max(sync_every - (since or 0), 0)
    if db.games_needing_plays(conn, MAX_PLAYS_CHECKS) or any("no plays yet" in n for n in notes):
        wait = min(wait, PLAYS_RETRY_MINUTES[0] * 60 * stretch)
    # Never sleep longer than 15 minutes, so the heartbeat stays fresh for the
    # health check. Waking up costs no API calls unless something is due.
    return min(max(wait, 60), MAX_SLEEP)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="run one pass and exit")
    args = ap.parse_args()
    settings = Settings.from_env()

    stopping = False

    def stop(signum, frame):  # Railway sends SIGTERM before replacing the service
        nonlocal stopping
        stopping = True
        log("stopping after this pass")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    with db.connect(os.environ["DATABASE_URL"]) as conn:
        for name in db.migrate(conn):
            log(f"applied migration {name}")
        client = cbbd.Client(on_call=lambda: db.count_api_call(conn))
        log(f"worker started; tracking {', '.join(settings.teams)}; limit {settings.monthly_limit} calls/month")
        while True:
            try:
                wait = run_once(conn, client, settings, dt.date.today())
            except Exception as e:  # keep running: one bad response shouldn't stop the worker
                log(f"error: {e!r}; retrying in 5 minutes")
                wait = 300
            if args.once or stopping:
                break
            log(f"next pass in {wait / 60:.0f} min")
            slept = 0.0
            while slept < wait and not stopping:  # sleep in short steps so SIGTERM is quick
                time.sleep(min(5, wait - slept))
                slept += 5


if __name__ == "__main__":
    main()
