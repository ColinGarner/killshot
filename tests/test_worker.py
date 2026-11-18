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
    assert wait == worker.MAX_SLEEP  # wakes for a heartbeat, but makes no calls


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


# --- live games (ESPN) -------------------------------------------------------

from killshot import live  # noqa: E402
from test_espn_translation import ESPN_IDS, load_espn  # noqa: E402

TODAY = dt.date(2026, 11, 18)


class FakeESPN:
    """Stands in for espn.summary: returns what the feed shows 'now', and counts reads."""

    def __init__(self, n_plays: int | None = None, fail: bool = False):
        self.summary, self.n_plays, self.fail, self.reads = load_espn(ESPN_IDS[KENTUCKY]), n_plays, fail, []

    def __call__(self, event_id):
        self.reads.append(event_id)
        if self.fail:
            raise OSError("ESPN is down")
        data = live.snapshot(self.summary, len(self.summary["plays"]) if self.n_plays is None else self.n_plays)
        if self.n_plays == 0:
            data["header"]["competitions"][0]["status"]["type"]["state"] = "pre"
        return data


def kentucky_on_now(**changes):
    """The Kentucky game on CBBD's schedule, tipped an hour ago, no plays yet."""
    return FakeCBBD([record(KENTUCKY, status="in_progress", startDate=iso(-1), **changes)])


def test_during_a_game_the_live_page_is_saved_and_the_next_read_is_in_30_seconds(conn):
    espn = FakeESPN(n_plays=250)
    wait = worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=espn)
    assert wait == worker.LIVE_POLL and espn.reads == [ESPN_IDS[KENTUCKY]]
    page, _ = db.live_page(conn, KENTUCKY, KANSAS)
    assert page["game"]["state"] == "in" and page["live"]["clock"].startswith(("1st", "2nd"))


def test_before_tip_off_nothing_is_saved_but_espn_is_watched(conn):
    wait = worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=FakeESPN(n_plays=0))
    assert wait == worker.LIVE_POLL and db.live_page(conn, KENTUCKY, KANSAS) is None


def test_after_espns_final_the_game_is_no_longer_polled(conn):
    espn = FakeESPN()  # the whole game: final
    worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=espn)
    page, _ = db.live_page(conn, KENTUCKY, KANSAS)
    assert (page["game"]["state"], page["game"]["pts"], page["game"]["opp_pts"]) == ("post", 89, 69)
    wait = worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=espn)
    assert len(espn.reads) == 1 and wait > worker.LIVE_POLL


def test_when_cbbds_plays_arrive_the_live_page_is_checked_and_removed(conn, capsys):
    worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=FakeESPN())
    # Ten minutes later the schedule sync sees the final, and CBBD has the plays.
    conn.execute("UPDATE worker_status SET last_schedule_sync_at = now() - interval '11 minutes'")
    client = FakeCBBD([record(KENTUCKY, startDate=iso(-3))], {KENTUCKY: load_data(KENTUCKY)["plays"]})
    worker.run_once(conn, client, SETTINGS, TODAY, fetch_espn=FakeESPN())
    assert "ESPN and CBBD agree, 89-69" in capsys.readouterr().out
    assert db.live_page(conn, KENTUCKY, KANSAS) is None
    assert sum(s.team.pts for s in db.stints_for(conn, KANSAS, 2027)) == 89  # CBBD's record


def test_a_live_score_that_disagrees_with_cbbd_is_logged_and_cbbd_wins(conn, games):
    worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=FakeESPN())
    page, _ = db.live_page(conn, KENTUCKY, KANSAS)
    page["game"]["pts"] = 88
    db.save_live(conn, KENTUCKY, KANSAS, page)
    (note,) = worker.reconcile(conn, games[KENTUCKY], db.live_pages(conn, KENTUCKY))
    assert "ESPN said 88-69, CBBD says 89-69" in note
    assert db.live_page(conn, KENTUCKY, KANSAS) is None


def test_an_espn_outage_is_logged_and_retried_without_stopping_the_worker(conn, capsys):
    wait = worker.run_once(conn, kentucky_on_now(), SETTINGS, TODAY, fetch_espn=FakeESPN(fail=True))
    assert wait == worker.LIVE_POLL
    assert "ESPN read failed" in capsys.readouterr().out


def test_the_worker_wakes_in_time_to_watch_the_next_tip(conn):
    client = FakeCBBD([record(KENTUCKY, status="scheduled", startDate=iso(0.2))])  # tips in 12 minutes
    espn = FakeESPN(n_plays=0)
    wait = worker.run_once(conn, client, SETTINGS, TODAY, fetch_espn=espn)
    assert espn.reads == [] and 60 <= wait <= 2 * 60 + 5  # wakes 10 minutes before tip


def test_no_espn_reads_on_a_day_without_games(conn):
    espn = FakeESPN()
    worker.run_once(conn, FakeCBBD([record(KENTUCKY, startDate=iso(-48))]), SETTINGS, TODAY, fetch_espn=espn)
    assert espn.reads == []
