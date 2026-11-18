"""Everything that reads or writes Postgres.

The SQL lives here in plain sight. Other modules hand this one `Game` objects
to save, and get `Stint` objects back to feed into `rollup`.
"""
import json
from pathlib import Path

import psycopg

from .box import Box
from .game import Game
from .stints import Stint

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
BOX_FIELDS = ["pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm", "oreb", "dreb", "to"]


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url)


# Any fixed number works; every process that migrates must use the same one.
MIGRATION_LOCK = 20_305  # 2305 is Kansas


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
                """INSERT INTO teams (id, name, abbr, color) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET name = excluded.name, abbr = excluded.abbr, color = excluded.color""",
                (team.id, team.name, team.abbr, team.color))

        for p in game.players.values():
            conn.execute(
                """INSERT INTO players (id, team_id, name, short_name, position) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET team_id = excluded.team_id, name = excluded.name,
                       short_name = excluded.short_name, position = excluded.position""",
                (p.id, p.team_id, p.name, p.short_name, p.position))

        conn.execute("DELETE FROM games WHERE id = %s", (game.id,))  # cascades to stints, win_prob, runs
        conn.execute(
            """INSERT INTO games (id, season, start_at, state, status, neutral_site,
                                  home_team_id, away_team_id, home_pts, away_pts, raw)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (game.id, game.season, game.start, game.state, game.status, game.neutral_site,
             game.home.id, game.away.id, game.home.score, game.away.score,
             json.dumps(raw) if raw is not None else None))

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


def stints_for(conn: psycopg.Connection, team_id: str, season: int) -> list[Stint]:
    """All of a team's stints in a season, as Stint objects ready for `rollup`."""
    columns = ", ".join([f"s.team_{f}" for f in BOX_FIELDS] + [f"s.opp_{f}" for f in BOX_FIELDS])
    rows = conn.execute(
        f"""SELECT s.team_id, s.player_ids, s.t_start, s.t_end, s.garbage, {columns}
            FROM stints s JOIN games g ON g.id = s.game_id
            WHERE s.team_id = %s AND g.season = %s
            ORDER BY g.start_at, s.t_start""",
        (team_id, season)).fetchall()
    n = len(BOX_FIELDS)
    stints = []
    for row in rows:
        team_id_, player_ids, t_start, t_end, garbage = row[:5]
        team_box = Box(**dict(zip(BOX_FIELDS, row[5:5 + n])))
        opp_box = Box(**dict(zip(BOX_FIELDS, row[5 + n:5 + 2 * n])))
        stints.append(Stint(team_id_, tuple(player_ids), t_start, t_end, garbage, team_box, opp_box))
    return stints


def player_names(conn: psycopg.Connection) -> dict[str, str]:
    """ESPN athlete id -> short name, for labeling lineups."""
    return dict(conn.execute("SELECT id, short_name FROM players").fetchall())
