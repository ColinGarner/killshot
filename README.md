# killshot

An NCAA men's basketball companion app. Tracks the most efficient lineups, win
probability and killshots (10-0 runs) for a team, from CollegeBasketballData.com play-by-play.
Built for any team; ships with Kansas.

## What's here

| Module | Job |
|---|---|
| `killshot/sources/cbbd.py` | The only code that talks to CollegeBasketballData.com, and translates its data |
| `killshot/sources/espn.py` | Reads ESPN's game summary for the live view (CBBD has no live plays); never saved as history |
| `killshot/plays.py` | Our own play format, so the basketball code never sees provider field names |
| `killshot/stints.py` | Splits a game into stretches with the same five players on the floor |
| `killshot/substitutions.py` | Fills in incomplete on-floor lists by replaying substitutions |
| `killshot/box.py` | Counting stats, possessions, ratings |
| `killshot/rollup.py` | Adds stints up into lineups, on/off splits, team totals |
| `killshot/events.py` | Win probability and killshots |
| `killshot/game.py` | One game → stints, win probability, killshots, data checks |
| `killshot/detail.py` | Puts a game page together (lineups, win probability, killshots), for finished and live games alike |
| `killshot/live.py` | Builds the live game page from ESPN while a game is on |
| `killshot/replay.py` | `killshot replay`: plays a finished game back through the live view, for testing |
| `migrations/*.sql` | The Postgres schema, one numbered file per change |
| `killshot/db.py` | All SQL: save a game, read a season's stints |
| `killshot/load.py` | Loads a team's finished games from CBBD into Postgres |
| `killshot/worker.py` | Runs forever: syncs schedules, reads ESPN every 30 s during games, saves each game after the final, within the API budget |
| `killshot/api.py` | The web API: JSON for the frontend, plus `/healthz` |
| `killshot/schemas.py` | The shape of every API response; the frontend's types are generated from these |
| `web/` | The React frontend (Vite, TypeScript, Tailwind, Recharts) |
| `killshot/reprocess.py` | Rebuilds every stored game from its saved raw data (no API calls) |
| `killshot/cli.py` | The `killshot` command: `start`, `migrate` and the tools below |
| `killshot/inspect.py`, `killshot/season.py` | Print a game or a season from the command line |

Choices behind the code are in [`docs/decisions.md`](docs/decisions.md).

## Run it locally

You need Python 3.11+, Node 26 and Postgres 16 (Postgres.app or `brew install postgresql@16`).
Node is pinned in `.tool-versions` (asdf: `asdf install`) and `web/.nvmrc` (nvm: `nvm install`).

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
| `killshot serve` | The same on a server (Railway): no build, no browser, open to the network |
| `killshot migrate` | Create the database if needed and apply migrations |
| `killshot test` | Run every test (Python and site); `killshot test python -k worker` narrows it |
| `killshot load --team Kansas --seasons 2026 2027` | Load a team's finished games from CBBD |
| `killshot inspect 372750` | Print one game (a CBBD id, or a saved file in `tests/fixtures/`) |
| `killshot season --season 2026` | Print a season: ratings, lineups, on/off |
| `killshot worker` | Run only the worker |
| `killshot reprocess` | Rebuild stored games from their saved raw data (no API calls) |
| `killshot replay 372750` | Play a finished game back as if live, about 80 seconds (`--speed 10` for slower) |

Every command reads `.env`; a variable set in your shell wins over the file.

### Developing

```bash
killshot test                   # everything; the Postgres tests use TEST_DATABASE_URL from .env
cd web && npm run dev           # live-reloading site on :5173 (run `killshot start` alongside for the API)
cd web && npm run gen:api       # after changing an API response: regenerate the TypeScript types
```

## Deploy (Railway)

One Railway service runs everything: the API, the site and the worker, from the
`Dockerfile`, with settings in `railway.json`. It deploys on every push to `main`.

**First time:**

1. In Railway, create a new project and add **PostgreSQL**.
2. Add a service from this GitHub repo. Railway finds `railway.json` and builds the `Dockerfile`.
3. On that service's **Variables** tab, add:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway fills in the database's address) |
   | `CBBD_API_KEY` | your CollegeBasketballData.com key |
   | `CBBD_MONTHLY_LIMIT` | `25000` (Tier 2 is 30,000; this leaves room for running it locally too) |
   | `TRACKED_TEAMS` | `Kansas` |

4. Under **Settings → Networking**, click **Generate Domain** for a public `*.up.railway.app` address.

The first deploy creates the tables and loads the last two seasons (about 40 CBBD
calls, a minute or so) before the site answers. Railway waits for `/healthz` to
say the worker is alive before switching traffic to a new deploy.

**Logs:** the service's Deployments tab shows the worker's lines (`schedule synced`,
`live: 2nd 12:41 54-48 ...`, `live check: ESPN and CBBD agree`).

`killshot serve` is what runs there: `killshot start` without the site build (the
image already has it) or the browser, listening on the network instead of just
the machine itself.

## Roadmap

1. Core library ✓
2. Database (Postgres schema, load history) ✓
   - 2.1 Migration lock ✓
   - 2.2 CollegeBasketballData.com as the data source ✓
   - 2.3 Fill incomplete lineups from substitutions ✓
3. Worker (schedule, finals) ✓
4. API ✓
6. Frontend ✓
7. **Live games and mobile** ← you are here
   - 7a Run it locally with `killshot start` ✓
   - 7.1 ESPN translator ✓
   - 7.2 Live state and `killshot replay` ✓
   - 7.3 Worker polls live games ✓
   - 7.4 API serves the live game ✓
   - 7.5 Live game page ✓
   - 7.6 Phone layout and Add to Home Screen (after the deploy)
5. **Railway deploy** ← this PR
8. Garbage-time toggle, foul trouble, scouting
