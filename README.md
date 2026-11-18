# killshot

An NCAA men's basketball companion app. Tracks the most efficient lineups, win
probability and killshots (10-0 runs) for a team, from CollegeBasketballData.com play-by-play.
Built for any team; ships with Kansas.

## What's here

| Module | Job |
|---|---|
| `killshot/sources/cbbd.py` | The only code that talks to CollegeBasketballData.com, and translates its data |
| `killshot/plays.py` | Our own play format, so the basketball code never sees provider field names |
| `killshot/stints.py` | Splits a game into stretches with the same five players on the floor |
| `killshot/substitutions.py` | Fills in incomplete on-floor lists by replaying substitutions |
| `killshot/box.py` | Counting stats, possessions, ratings |
| `killshot/rollup.py` | Adds stints up into lineups, on/off splits, team totals |
| `killshot/events.py` | Win probability and killshots |
| `killshot/game.py` | One game → stints, win probability, killshots, data checks |
| `migrations/*.sql` | The Postgres schema, one numbered file per change |
| `killshot/db.py` | All SQL: save a game, read a season's stints |
| `killshot/load.py` | Loads a team's finished games from CBBD into Postgres |
| `killshot/worker.py` | Runs forever: syncs schedules, saves each game after the final, within the API budget |
| `killshot/api.py` | The web API: JSON for the frontend, plus `/healthz` |
| `killshot/schemas.py` | The shape of every API response; the frontend's types are generated from these |
| `web/` | The React frontend (Vite, TypeScript, Tailwind, Recharts) |
| `killshot/reprocess.py` | Rebuilds every stored game from its saved raw data (no API calls) |
| `killshot/cli.py` | The `killshot` command: `start`, `migrate` and the tools below |
| `killshot/inspect.py`, `killshot/season.py` | Print a game or a season from the command line |

Choices behind the code are in [`docs/decisions.md`](docs/decisions.md).

## Run it locally

You need Python 3.11+, Node 26 and Postgres 16 (Postgres.app or `brew install postgresql@16`).

```bash
pip install -e ".[dev]"        # once: installs the `killshot` command
cp .env.sample .env            # once: then add your CollegeBasketballData key to .env
killshot start                 # http://localhost:8000 — Ctrl-C to stop
```

The first `killshot start` creates the database, builds the site and loads Kansas's
last two seasons (about 40 API calls). After that it starts in a couple of seconds.
The worker keeps new games coming in while it runs.

### Commands

| Command | What it does |
|---|---|
| `killshot start` | Migrate, build the site if it changed, then run the site and worker |
| `killshot migrate` | Create the database if needed and apply migrations |
| `killshot test` | Run every test (Python and site); `killshot test python -k worker` narrows it |
| `killshot load --team Kansas --seasons 2026 2027` | Load a team's finished games from CBBD |
| `killshot inspect 372750` | Print one game (a CBBD id, or a saved file in `tests/fixtures/`) |
| `killshot season --season 2026` | Print a season: ratings, lineups, on/off |
| `killshot worker` | Run only the worker |
| `killshot reprocess` | Rebuild stored games from their saved raw data (no API calls) |

Every command reads `.env`; a variable set in your shell wins over the file.

### Developing

```bash
killshot test                   # everything; the Postgres tests use TEST_DATABASE_URL from .env
cd web && npm run dev           # live-reloading site on :5173 (run `killshot start` alongside for the API)
cd web && npm run gen:api       # after changing an API response: regenerate the TypeScript types
```

## Roadmap

1. Core library ✓
2. Database (Postgres schema, load history) ✓
   - 2.1 Migration lock ✓
   - 2.2 CollegeBasketballData.com as the data source ✓
   - 2.3 Fill incomplete lineups from substitutions ✓
3. Worker (schedule, finals) ✓
4. API ✓
6. Frontend ✓
7. **Live games and mobile** ← you are here (7a: run it locally with `killshot start`)
5. Railway deploy (everything at once, after 6 and 7)
8. Garbage-time toggle, foul trouble, scouting
