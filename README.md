# killshot

An NCAA men's basketball companion app. Tracks the most efficient lineups, win
probability and killshots (10-0 runs) for a team, rebuilt from ESPN play-by-play.
Built for any team; ships with Kansas.

## What's here (Milestone 1: core library)

| Module | Job |
|---|---|
| `killshot/espn.py` | The only code that talks to ESPN |
| `killshot/stints.py` | Rebuilds who was on the floor, from substitutions |
| `killshot/box.py` | Counting stats, possessions, ratings |
| `killshot/rollup.py` | Adds stints up into lineups, on/off splits, team totals |
| `killshot/events.py` | Win probability and killshots |
| `killshot/game.py` | One ESPN game file → everything above |
| `killshot/inspect.py` | Prints a game from the command line |

Choices behind the code are in [`docs/decisions.md`](docs/decisions.md).

## Try it

```bash
pip install -e ".[dev]"
python -m killshot.inspect tests/fixtures/401909786.json.gz   # KU 89, Kentucky 69
python -m killshot.inspect 401909787                           # fetches UNLV from ESPN
pytest
```

## Roadmap

1. **Core library** ← you are here
2. Database (Postgres schema, load history)
3. Worker (schedule, finals)
4. API
5. Railway deploy
6. Frontend
7. Live games and mobile
8. Garbage-time toggle, foul trouble, scouting
