"""Everything that reads or writes Postgres.

The SQL lives here in plain sight. Other modules hand this one `Game` objects
to save, and get `Stint` objects back to feed into `rollup`.
"""
import datetime as dt
import json
from pathlib import Path

import psycopg
import psycopg.sql

from .box import Box
from .game import Game
from .stints import Stint

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
BOX_FIELDS = ["pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm", "oreb", "dreb", "to"]


def connect(url: str) -> psycopg.Connection:
    """Open a connection in autocommit mode: each statement saves immediately,
    except inside `with conn.transaction():`, where a group saves all together."""
    return psycopg.connect(url, autocommit=True)


def ensure_database(url: str) -> bool:
    """Create the database named in `url` if it doesn't exist yet. Returns True if it was created.

    Connects to the server's built-in `postgres` database to do it, so a fresh
    local Postgres needs no manual `createdb`.
    """
    info = psycopg.conninfo.conninfo_to_dict(url)
    name = info.get("dbname")
    try:
        psycopg.connect(url).close()
        return False
    except psycopg.OperationalError as e:
        if not name or "does not exist" not in str(e):
            raise  # Postgres isn't running, or the login is wrong: nothing to create
    admin = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
    return True


def count_api_call(conn: psycopg.Connection) -> None:
    """Record one CBBD API call against this calendar month."""
    conn.execute("""INSERT INTO api_usage (month, calls) VALUES (to_char(now(), 'YYYY-MM'), 1)
                    ON CONFLICT (month) DO UPDATE SET calls = api_usage.calls + 1""")


def api_calls_this_month(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT calls FROM api_usage WHERE month = to_char(now(), 'YYYY-MM')").fetchone()
    return row[0] if row else 0


# Any fixed number works; every process that migrates must use the same one.
MIGRATION_LOCK = 20_305


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply any migrations/NNN_*.sql files that haven't run yet, in order.

    Each file runs once; its name is recorded in schema_migrations.
    Returns the names applied this time.

    Everything happens in one transaction, so a failing file undoes the whole
    run. The advisory lock makes a second process that starts migrating at the
    same moment (e.g. the web service and the worker on Railway) wait until the
    first one finishes. It then sees the files already applied and does nothing.
    """
    applied = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))  # released at commit
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        for path in migration_files():
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied


def migration_files() -> list[Path]:
    """The migration files, in the order they run."""
    return sorted(MIGRATIONS.glob("*.sql"))


def save_game(conn: psycopg.Connection, game: Game, raw: dict | None = None) -> None:
    """Write one game and everything derived from it, replacing any earlier copy.

    It all happens in one transaction: either the whole game is saved or none
    of it is. Deleting the old rows first means saving the same game twice
    never creates duplicates.
    """
    with conn.transaction():
        for team in (game.home, game.away):
            conn.execute(
                """INSERT INTO teams (id, name) VALUES (%s, %s)
                   ON CONFLICT (id) DO UPDATE SET name = excluded.name""",
                (team.id, team.name))

        for p in game.players.values():
            conn.execute(
                """INSERT INTO players (id, team_id, name, short_name) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET team_id = excluded.team_id, name = excluded.name,
                       short_name = excluded.short_name""",
                (p.id, p.team_id, p.name, p.short_name))

        conn.execute("DELETE FROM games WHERE id = %s", (game.id,))  # cascades to stints, win_prob, runs
        conn.execute(
            """INSERT INTO games (id, espn_id, season, start_at, state, status, neutral_site,
                                  home_team_id, away_team_id, home_pts, away_pts, raw, plays_saved_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       CASE WHEN %s THEN now() END)""",
            (game.id, game.espn_id, game.season, game.start, game.state, game.status, game.neutral_site,
             game.home.id, game.away.id, game.home.score, game.away.score,
             json.dumps(raw) if raw is not None else None,
             bool(raw and raw.get("plays"))))

        columns = ", ".join([f"team_{f}" for f in BOX_FIELDS] + [f"opp_{f}" for f in BOX_FIELDS])
        placeholders = ", ".join(["%s"] * (6 + 2 * len(BOX_FIELDS)))
        for team_id, stints in game.stints.items():
            for s in stints:
                conn.execute(
                    f"INSERT INTO stints (game_id, team_id, player_ids, t_start, t_end, garbage, {columns}) "
                    f"VALUES ({placeholders})",
                    [game.id, team_id, list(s.player_ids), s.t_start, s.t_end, s.garbage]
                    + [getattr(s.team, f) for f in BOX_FIELDS] + [getattr(s.opp, f) for f in BOX_FIELDS])

        for w in game.win_prob:
            conn.execute(
                """INSERT INTO win_prob (game_id, t, home_wp, home_pts, away_pts) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (game_id, t) DO UPDATE SET home_wp = excluded.home_wp,
                       home_pts = excluded.home_pts, away_pts = excluded.away_pts""",
                (game.id, w.t, w.home_wp, w.home_pts, w.away_pts))

        for r in game.runs:
            conn.execute(
                """INSERT INTO runs (game_id, team_id, pts, t0, t1, home0, away0, home1, away1)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (game.id, r.team_id, r.pts, r.t0, r.t1, r.home0, r.away0, r.home1, r.away1))


def saved_final_game_ids(conn: psycopg.Connection) -> set[str]:
    """Games already stored as finished, so a reload can skip them."""
    return {row[0] for row in conn.execute("SELECT id FROM games WHERE state = 'post'")}


def stints_for(conn: psycopg.Connection, team_id: str, season: int | None = None,
               game_id: str | None = None) -> list[Stint]:
    """A team's stints for a season, or for one game, as Stint objects ready for `rollup`."""
    columns = ", ".join([f"s.team_{f}" for f in BOX_FIELDS] + [f"s.opp_{f}" for f in BOX_FIELDS])
    rows = conn.execute(
        f"""SELECT s.team_id, s.player_ids, s.t_start, s.t_end, s.garbage, {columns}
            FROM stints s JOIN games g ON g.id = s.game_id
            WHERE s.team_id = %(team)s
              AND (%(season)s::int IS NULL OR g.season = %(season)s)
              AND (%(game)s::text IS NULL OR g.id = %(game)s)
            ORDER BY g.start_at, s.t_start""",
        {"team": team_id, "season": season, "game": game_id}).fetchall()
    n = len(BOX_FIELDS)
    stints = []
    for row in rows:
        team_id_, player_ids, t_start, t_end, garbage = row[:5]
        team_box = Box(**dict(zip(BOX_FIELDS, row[5:5 + n])))
        opp_box = Box(**dict(zip(BOX_FIELDS, row[5 + n:5 + 2 * n])))
        stints.append(Stint(team_id_, tuple(player_ids), t_start, t_end, garbage, team_box, opp_box))
    return stints


def player_names(conn: psycopg.Connection) -> dict[str, str]:
    """Player id -> short name, for labeling lineups."""
    return dict(conn.execute("SELECT id, short_name FROM players").fetchall())


def players(conn: psycopg.Connection) -> dict[str, dict]:
    """Player id -> {"id", "name", "short_name"}, for display."""
    return {pid: {"id": pid, "name": name, "short_name": short}
            for pid, name, short in conn.execute("SELECT id, name, short_name FROM players").fetchall()}


# --- for the worker ------------------------------------------------------------

def upsert_scheduled_game(conn: psycopg.Connection, record: dict, state: str) -> None:
    """Store or refresh a game from CBBD's schedule (status, time, score), without
    touching plays or stints already saved for it.

    The CBBD game record is kept in raw["game"], so the worker has it when it's
    time to fetch the plays.
    """
    with conn.transaction():
        for team_id, name in ((record["homeTeamId"], record["homeTeam"]), (record["awayTeamId"], record["awayTeam"])):
            conn.execute("INSERT INTO teams (id, name) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET name = excluded.name",
                         (str(team_id), name))
        conn.execute(
            """INSERT INTO games (id, espn_id, season, start_at, state, status, neutral_site,
                                  home_team_id, away_team_id, home_pts, away_pts, raw)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, jsonb_build_object('game', %s::jsonb))
               ON CONFLICT (id) DO UPDATE SET
                   espn_id = excluded.espn_id, start_at = excluded.start_at, state = excluded.state,
                   status = excluded.status, neutral_site = excluded.neutral_site,
                   home_team_id = excluded.home_team_id, away_team_id = excluded.away_team_id,
                   home_pts = excluded.home_pts, away_pts = excluded.away_pts,
                   -- keep any stored plays; just refresh the game record
                   raw = coalesce(games.raw, '{}'::jsonb) || jsonb_build_object('game', %s::jsonb)""",
            (str(record["id"]), record.get("sourceId"), record["season"], record["startDate"], state,
             record["status"].replace("_", " ").title(), bool(record.get("neutralSite")),
             str(record["homeTeamId"]), str(record["awayTeamId"]),
             record.get("homePoints"), record.get("awayPoints"),
             json.dumps(record), json.dumps(record)))


def games_needing_plays(conn: psycopg.Connection, max_checks: int) -> list[tuple[str, dict]]:
    """Finished games whose plays we don't have yet and are due for another try.
    Returns (game id, CBBD game record) pairs."""
    return conn.execute(
        """SELECT id, raw -> 'game' FROM games
           WHERE state = 'post' AND plays_saved_at IS NULL AND raw ? 'game'
             AND plays_checks < %s AND (next_plays_check_at IS NULL OR next_plays_check_at <= now())
           ORDER BY start_at""", (max_checks,)).fetchall()


def plays_not_ready(conn: psycopg.Connection, game_id: str, retry_in_minutes: float) -> int:
    """CBBD had no plays for a finished game yet: count the try and schedule the next.
    Returns how many tries have now come up empty."""
    return conn.execute(
        """UPDATE games SET plays_checks = plays_checks + 1,
                            next_plays_check_at = now() + make_interval(mins => %s)
           WHERE id = %s RETURNING plays_checks""", (retry_in_minutes, game_id)).fetchone()[0]


def plays_checks(conn: psycopg.Connection, game_id: str) -> int:
    return conn.execute("SELECT plays_checks FROM games WHERE id = %s", (game_id,)).fetchone()[0]


def game_near(conn: psycopg.Connection, team_names: list[str], hours_before: float, hours_after: float) -> bool:
    """Is a game for one of these teams starting soon, or recently started?"""
    row = conn.execute(
        """SELECT 1 FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams a ON a.id = g.away_team_id
           WHERE (h.name = ANY(%s) OR a.name = ANY(%s))
             AND g.start_at BETWEEN now() - make_interval(hours => %s) AND now() + make_interval(hours => %s)
           LIMIT 1""", (team_names, team_names, hours_after, hours_before)).fetchone()
    return row is not None


def heartbeat(conn: psycopg.Connection, note: str, synced_schedule: bool = False) -> None:
    """Record that the worker is alive (and, if it just did, when it synced schedules)."""
    conn.execute(
        """INSERT INTO worker_status (id, heartbeat_at, last_schedule_sync_at, note)
           VALUES (1, now(), CASE WHEN %s THEN now() END, %s)
           ON CONFLICT (id) DO UPDATE SET heartbeat_at = now(), note = excluded.note,
               last_schedule_sync_at = CASE WHEN %s THEN now() ELSE worker_status.last_schedule_sync_at END""",
        (synced_schedule, note, synced_schedule))


def seconds_since_schedule_sync(conn: psycopg.Connection) -> float | None:
    row = conn.execute("SELECT extract(epoch FROM now() - last_schedule_sync_at) FROM worker_status WHERE id = 1").fetchone()
    return float(row[0]) if row and row[0] is not None else None


# --- for the API ---------------------------------------------------------------

def team_ids(conn: psycopg.Connection, names: list[str]) -> dict[str, str]:
    """Team id -> name, for the given team names (as CBBD spells them)."""
    return dict(conn.execute("SELECT id, name FROM teams WHERE name = ANY(%s)", (names,)).fetchall())


def games_for_team(conn: psycopg.Connection, team_id: str, season: int | None = None,
                   game_id: str | None = None) -> list[dict]:
    """A team's games for a season (or just one game), oldest first, as plain dicts."""
    cur = conn.execute(
        """SELECT g.id, g.start_at, g.state, g.status, g.neutral_site,
                  g.home_team_id, h.name AS home_name, g.away_team_id, a.name AS away_name,
                  g.home_pts, g.away_pts, g.plays_saved_at IS NOT NULL AS has_plays,
                  coalesce((g.raw -> 'game' ->> 'startTimeTbd')::boolean, false) AS time_tbd
           FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams a ON a.id = g.away_team_id
           WHERE %(team)s IN (g.home_team_id, g.away_team_id)
             AND (%(season)s::int IS NULL OR g.season = %(season)s)
             AND (%(game)s::text IS NULL OR g.id = %(game)s)
           ORDER BY g.start_at""", {"team": team_id, "season": season, "game": game_id})
    names = [c.name for c in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def win_prob_for_game(conn: psycopg.Connection, game_id: str) -> list[tuple]:
    """(t, home_wp, home_pts, away_pts) rows, in game order."""
    return conn.execute("SELECT t, home_wp, home_pts, away_pts FROM win_prob WHERE game_id = %s ORDER BY t",
                        (game_id,)).fetchall()


def runs_for_game(conn: psycopg.Connection, game_id: str) -> list[tuple]:
    """(team_id, pts, t0, t1, home0, away0, home1, away1) rows, in game order."""
    return conn.execute(
        "SELECT team_id, pts, t0, t1, home0, away0, home1, away1 FROM runs WHERE game_id = %s ORDER BY t0",
        (game_id,)).fetchall()


def worker_heartbeat_age(conn: psycopg.Connection) -> tuple[float | None, str | None]:
    """Seconds since the worker's last heartbeat, and its last note. (None, None) if it never ran."""
    row = conn.execute("SELECT extract(epoch FROM now() - heartbeat_at), note FROM worker_status WHERE id = 1").fetchone()
    return (float(row[0]), row[1]) if row else (None, None)


# --- live games ------------------------------------------------------------------

def espn_id(conn: psycopg.Connection, game_id: str) -> str | None:
    """ESPN's event id for one of our games (CBBD lists it as sourceId)."""
    row = conn.execute("SELECT coalesce(espn_id, raw -> 'game' ->> 'sourceId') FROM games WHERE id = %s",
                       (game_id,)).fetchone()
    return row[0] if row else None


def save_live(conn: psycopg.Connection, game_id: str, team_id: str, payload: dict) -> None:
    conn.execute(
        """INSERT INTO live_state (game_id, team_id, payload) VALUES (%s, %s, %s)
           ON CONFLICT (game_id, team_id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()""",
        (game_id, team_id, json.dumps(payload)))


def live_page(conn: psycopg.Connection, game_id: str, team_id: str) -> tuple[dict, dt.datetime] | None:
    """(the live game page, when it was saved), or None if the game isn't live."""
    return conn.execute("SELECT payload, updated_at FROM live_state WHERE game_id = %s AND team_id = %s",
                        (game_id, team_id)).fetchone()


def live_games(conn: psycopg.Connection, team_id: str) -> dict[str, dict]:
    """Game id -> the live page's game summary, for every live game of one team."""
    return dict(conn.execute("SELECT game_id, payload -> 'game' FROM live_state WHERE team_id = %s",
                             (team_id,)).fetchall())


def clear_live(conn: psycopg.Connection, game_id: str) -> None:
    conn.execute("DELETE FROM live_state WHERE game_id = %s", (game_id,))


def games_to_watch(conn: psycopg.Connection, team_names: list[str], minutes_before: float,
                   hours_after: float) -> list[tuple[str, str | None, str]]:
    """Tracked teams' games to poll ESPN for: starting within `minutes_before`, or
    started within `hours_after` and not yet final on ESPN or saved from CBBD.
    Returns (game id, ESPN event id, tracked team id) rows; a game with two
    tracked teams appears twice."""
    return conn.execute(
        """SELECT g.id, coalesce(g.espn_id, g.raw -> 'game' ->> 'sourceId'), t.id
           FROM games g JOIN teams t ON t.id IN (g.home_team_id, g.away_team_id)
           WHERE t.name = ANY(%s) AND g.plays_saved_at IS NULL
             AND g.start_at BETWEEN now() - make_interval(hours => %s) AND now() + make_interval(mins => %s)
             AND NOT EXISTS (SELECT 1 FROM live_state l
                             WHERE l.game_id = g.id AND l.payload -> 'game' ->> 'state' = 'post')
           ORDER BY g.start_at, t.id""", (team_names, hours_after, minutes_before)).fetchall()


def seconds_until_next_tip(conn: psycopg.Connection, team_names: list[str]) -> float | None:
    """Seconds until the next tracked game's tip-off, or None if none is scheduled."""
    row = conn.execute(
        """SELECT extract(epoch FROM min(g.start_at) - now()) FROM games g
           JOIN teams t ON t.id IN (g.home_team_id, g.away_team_id)
           WHERE t.name = ANY(%s) AND g.start_at > now()""", (team_names,)).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def live_pages(conn: psycopg.Connection, game_id: str) -> dict[str, dict]:
    """Team id -> live page, for every tracked team's live row of one game."""
    return dict(conn.execute("SELECT team_id, payload FROM live_state WHERE game_id = %s", (game_id,)).fetchall())
