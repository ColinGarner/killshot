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
| `killshot/inspect.py`, `killshot/season.py` | Print a game or a season from the command line |

Choices behind the code are in [`docs/decisions.md`](docs/decisions.md).

## Try it

```bash
pip install -e ".[dev]"
python -m killshot.inspect tests/fixtures/cbbd_372750.json.gz  # KU 89, Kentucky 69, no database or API key needed

docker compose up -d db                                         # local Postgres
export DATABASE_URL=postgresql://killshot:killshot@localhost:5432/killshot
export CBBD_API_KEY=...                                         # your CollegeBasketballData.com key
python -m killshot.load --team Kansas --seasons 2026 2027       # ~40 games, ~41 API calls
python -m killshot.season --season 2026                         # team ratings, lineups, on/off
python -m killshot.worker --once                                # one worker pass; drop --once to run forever
uvicorn killshot.api:app --reload                               # the API; browse http://localhost:8000/docs
psql "$DATABASE_URL" -c "SELECT sum(team_pts), sum(opp_pts) FROM stints WHERE team_id = '131'"

pytest   # set TEST_DATABASE_URL to a throwaway database to include the Postgres tests
```

### Frontend (`web/`, Node 26)

```bash
cd web
npm ci
npm run dev        # http://localhost:5173, with API calls forwarded to uvicorn on :8000
npm run gen:api    # after changing an API response: regenerate the TypeScript types
npm test && npm run build   # build output in web/dist, served by the API at http://localhost:8000
```

## Roadmap

1. Core library ✓
2. Database (Postgres schema, load history) ✓
   - 2.1 Migration lock ✓
   - 2.2 CollegeBasketballData.com as the data source ✓
   - 2.3 Fill incomplete lineups from substitutions ✓
3. Worker (schedule, finals) ✓
4. API ✓
6. **Frontend** ← you are here (6.1 Game log; 6.2 Season next)
7. Live games and mobile
5. Railway deploy (everything at once, after 6 and 7)
8. Garbage-time toggle, foul trouble, scouting
