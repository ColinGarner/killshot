"""Saving games to Postgres and reading them back gives the same numbers.

Needs TEST_DATABASE_URL pointing at an empty, throwaway database. The tests
drop and recreate every table, so never point it at real data.
Skipped when TEST_DATABASE_URL isn't set.
"""
import os

import pytest

from killshot import db, rollup
from conftest import FORDHAM, KANSAS, KENTUCKY, KENTUCKY_TEAM, MTSU, UNLV, load_data

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture()
def conn():
    with db.connect(URL) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        db.migrate(c)
        yield c


def test_migrations_run_once(conn):
    assert db.migrate(conn) == []  # already applied by the fixture


def test_stints_round_trip_through_postgres(conn, games):
    for event in (FORDHAM, MTSU, KENTUCKY):
        db.save_game(conn, games[event], load_data(event))
    totals = rollup.team_totals(db.stints_for(conn, KANSAS, 2027))
    assert (totals["ortg"], totals["drtg"], totals["net"]) == (122.7, 80.4, 42.2)


def test_saving_a_game_twice_does_not_duplicate_it(conn, games):
    db.save_game(conn, games[UNLV])
    db.save_game(conn, games[UNLV])
    counts = conn.execute(
        "SELECT (SELECT count(*) FROM games), (SELECT count(*) FROM stints WHERE team_id = %s)",
        (KANSAS,)).fetchone()
    assert counts == (1, len(games[UNLV].stints[KANSAS]))


def test_both_teams_and_the_killshot_are_stored(conn, games):
    db.save_game(conn, games[KENTUCKY])
    teams = {row[0] for row in conn.execute("SELECT DISTINCT team_id FROM stints")}
    assert teams == {KANSAS, KENTUCKY_TEAM}
    run = conn.execute("SELECT team_id, pts, home0, away0, home1, away1 FROM runs").fetchone()
    assert run == (KANSAS, 12, 51, 41, 63, 41)


def test_points_can_be_summed_in_plain_sql(conn, games):
    db.save_game(conn, games[KENTUCKY])
    pts = conn.execute(
        "SELECT sum(team_pts), sum(opp_pts) FROM stints WHERE team_id = %s", (KANSAS,)).fetchone()
    assert pts == (89, 69)


def test_api_calls_are_counted_per_month(conn):
    for _ in range(3):
        db.count_api_call(conn)
    assert db.api_calls_this_month(conn) == 3
