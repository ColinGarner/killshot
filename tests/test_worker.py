"""The worker keeps games up to date on its own, within the API budget.

These use a fake CBBD client (no network) and a real Postgres (TEST_DATABASE_URL).
"""
import copy
import datetime as dt

import pytest

from killshot import db, worker
from conftest import KANSAS, KENTUCKY, UNLV, load_data

SETTINGS = worker.Settings(teams=["Kansas"], monthly_limit=5000)


class FakeCBBD:
    """Stands in for cbbd.Client: serves the schedule and plays we give it, and
    records what was asked for."""

    def __init__(self, schedule: list[dict], plays: dict[str, list] | None = None):
        self.schedule, self.plays_by_game, self.calls = schedule, plays or {}, []

    def games(self, team, season):
        self.calls.append(("games", team, season))
        return copy.deepcopy(self.schedule)

    def plays(self, game_id):
        self.calls.append(("plays", game_id))
        return copy.deepcopy(self.plays_by_game.get(str(game_id), []))


def record(game_id: str, **changes) -> dict:
    """CBBD's game record for one of our saved games, optionally altered."""
    r = copy.deepcopy(load_data(game_id)["game"])
    r.update(changes)
    return r


def iso(hours_from_now: float) -> str:
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours_from_now)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_college_seasons_are_named_for_the_year_they_end():
    assert worker.current_season(dt.date(2026, 11, 18)) == 2027
    assert worker.current_season(dt.date(2027, 3, 20)) == 2027
    assert worker.current_season(dt.date(2027, 9, 1)) == 2028


def test_polling_slows_at_90_percent_of_the_allowance_and_stops_at_100():
    assert worker.budget_multiplier(4000, 5000) == 1.0
    assert worker.budget_multiplier(4500, 5000) == 4.0
    assert worker.budget_multiplier(5000, 5000) is None


def test_a_finished_game_is_saved_with_its_plays(conn):
    client = FakeCBBD([record(KENTUCKY)], {KENTUCKY: load_data(KENTUCKY)["plays"]})
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    stints = db.stints_for(conn, KANSAS, 2027)
    assert sum(s.team.pts for s in stints) == 89
    assert conn.execute("SELECT plays_saved_at IS NOT NULL FROM games WHERE id = %s", (KENTUCKY,)).fetchone()[0]


def test_a_final_without_plays_yet_is_retried_later_not_immediately(conn):
    client = FakeCBBD([record(UNLV)], {})  # final on the schedule, but CBBD has no plays yet
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert db.plays_checks(conn, UNLV) == 1
    assert db.stints_for(conn, KANSAS, 2027) == []

    client.calls.clear()
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert ("plays", UNLV) not in client.calls  # the next try isn't due for 5 minutes

    # Five minutes later, CBBD has published the plays.
    conn.execute("UPDATE games SET next_plays_check_at = now() - interval '1 second' WHERE id = %s", (UNLV,))
    client.plays_by_game[UNLV] = load_data(UNLV)["plays"]
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert sum(s.team.pts for s in db.stints_for(conn, KANSAS, 2027)) == 102


def test_refreshing_the_schedule_keeps_plays_already_saved(conn):
    client = FakeCBBD([record(KENTUCKY)], {KENTUCKY: load_data(KENTUCKY)["plays"]})
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    before = len(db.stints_for(conn, KANSAS, 2027))
    worker.sync_schedules(conn, client, SETTINGS, 2027)  # same game comes back on the schedule
    assert len(db.stints_for(conn, KANSAS, 2027)) == before
    raw = conn.execute("SELECT raw FROM games WHERE id = %s", (KENTUCKY,)).fetchone()[0]
    assert raw["plays"] and raw["game"]["id"] == int(KENTUCKY)


def test_games_with_an_unknown_opponent_are_skipped_until_its_known(conn):
    tbd = record(UNLV, id=999001, status="scheduled", startDate=iso(48), homeTeam="TBD", homeTeamId=1543)
    worker.sync_schedules(conn, FakeCBBD([tbd]), SETTINGS, 2027)
    assert conn.execute("SELECT count(*) FROM games").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM teams WHERE name = 'TBD'").fetchone()[0] == 0


def test_schedule_syncs_every_10_minutes_around_a_game_and_every_6_hours_otherwise(conn):
    soon = record(UNLV, id=999002, status="scheduled", startDate=iso(0.5), homePoints=None, awayPoints=None)
    wait = worker.run_once(conn, FakeCBBD([soon]), SETTINGS, dt.date(2026, 11, 18))
    # The first pass synced with the idle interval (nothing was stored yet); the next decides from the game.
    conn.execute("UPDATE worker_status SET last_schedule_sync_at = now() - interval '11 minutes'")
    client = FakeCBBD([soon])
    wait = worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert ("games", "Kansas", 2027) in client.calls
    assert wait == worker.GAME_DAY_SYNC

    far = record(UNLV, id=999002, status="scheduled", startDate=iso(72), homePoints=None, awayPoints=None)
    conn.execute("UPDATE worker_status SET last_schedule_sync_at = now() - interval '11 minutes'")
    worker.run_once(conn, FakeCBBD([far]), SETTINGS, dt.date(2026, 11, 18))
    client = FakeCBBD([far])
    wait = worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert client.calls == []  # 6 hours haven't passed
    assert wait > 5 * 60 * 60


def test_no_calls_at_all_once_the_monthly_allowance_is_used(conn):
    conn.execute("INSERT INTO api_usage (month, calls) VALUES (to_char(now(), 'YYYY-MM'), 5000)")
    client = FakeCBBD([record(KENTUCKY)], {KENTUCKY: load_data(KENTUCKY)["plays"]})
    worker.run_once(conn, client, SETTINGS, dt.date(2026, 11, 18))
    assert client.calls == []
    note = conn.execute("SELECT note FROM worker_status").fetchone()[0]
    assert "limit reached" in note


def test_every_pass_records_a_heartbeat(conn):
    worker.run_once(conn, FakeCBBD([]), SETTINGS, dt.date(2026, 11, 18))
    age = conn.execute("SELECT extract(epoch FROM now() - heartbeat_at) FROM worker_status").fetchone()[0]
    assert age < 5
