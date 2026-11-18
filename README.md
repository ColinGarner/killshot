# killshot

An NCAA men's basketball companion app. Tracks the most efficient lineups, win
probability and killshots (10-0 runs) for a team, rebuilt from ESPN play-by-play.
Built for any team; ships with Kansas.

## What's here

| Module | Job |
|---|---|
| `killshot/espn.py` | The only code that talks to ESPN |
| `killshot/stints.py` | Rebuilds who was on the floor, from substitutions |
| `killshot/box.py` | Counting stats, possessions, ratings |
| `killshot/rollup.py` | Adds stints up into lineups, on/off splits, team totals |
| `killshot/events.py` | Win probability and killshots |
| `killshot/game.py` | One ESPN game file → everything above |
| `migrations/*.sql` | The Postgres schema, one numbered file per change |
| `killshot/db.py` | All SQL: save a game, read a season's stints |
| `killshot/load.py` | Loads a team's finished games from ESPN into Postgres |
| `killshot/inspect.py`, `killshot/season.py` | Print a game or a season from the command line |

Choices behind the code are in [`docs/decisions.md`](docs/decisions.md).

## Try it

```bash
pip install -e ".[dev]"
python -m killshot.inspect tests/fixtures/401909786.json.gz   # KU 89, Kentucky 69, no database needed

docker compose up -d db                                         # local Postgres
export DATABASE_URL=postgresql://killshot:killshot@localhost:5432/killshot
python -m killshot.load --team 2305 --seasons 2026 2027         # ~40 games, about a minute
python -m killshot.season --season 2026                         # team ratings, lineups, on/off
psql "$DATABASE_URL" -c "SELECT sum(team_pts), sum(opp_pts) FROM stints WHERE team_id = '2305'"

pytest   # set TEST_DATABASE_URL to a throwaway database to include the Postgres tests
```

## Roadmap

1. Core library ✓
2. **Database (Postgres schema, load history)** ← you are here
3. Worker (schedule, finals)
4. API
5. Railway deploy
6. Frontend
7. Live games and mobile
8. Garbage-time toggle, foul trouble, scouting
