# Killshot

KU men's basketball analytics: best and worst lineups, rolling win probability,
killshots (10-0 runs), season lineups and on/off, and a live game page built
for a phone in Allen Fieldhouse. Live at https://killshot.up.railway.app.

## Working with Colin

- **Colin doesn't write the code; Claude does.** He reviews PRs, runs the app, and
  knows basketball far better than the code. He's strong in React, lighter in Python.
- **Small PRs, one milestone or fix each.** Stack them when they build on each other.
  Never commit to `main`; branch first. Don't force-push; make a new branch instead.
- **Every PR description has these sections:** what changed (plain words first),
  **Read these** (files in reading order), **Check it yourself** (exact commands, each
  in its own `bash` block), **Python notes** (or React notes) for anything idiomatic,
  and **Left out on purpose**.
- **Keep the code simple and readable** over clever. Plain SQL, no ORM, few dependencies.
- **Explain basketball results in plain words** with the numbers that support them.
  Check claims against the data before making them (it caught real mistakes before).
- **No Docker locally.** Docker is only for the Railway image.

## Run and check it

Everything goes through one command, `killshot` (`pip install -e ".[dev]"` in a venv).
Settings come from `.env` (copy `.env.sample`); shell variables win over the file.

```bash
killshot start                      # migrate, build site if changed, run site + worker, open browser
killshot test                       # all tests: pytest + Vitest (prints "Python: passed  Site: passed")
killshot test python -k worker      # narrow the Python tests
killshot test web                   # just the site's tests
killshot replay 372750 --speed 5    # play a finished game back as if live (tests the live page)
killshot inspect 372750             # print one game's lineups, killshots and data checks
killshot migrate                    # create the database if needed and apply migrations
```

**After a change, validate it like this:**
1. `killshot test` must pass (CI runs the same: pytest with Postgres, then the site's
   gen:api diff check, typecheck, Vitest with `TZ=UTC`, and build).
2. Changed `killshot/schemas.py`? Run `cd web && npm run gen:api` and commit the
   regenerated `web/src/api/schema.d.ts` and `web/openapi.json`, or CI fails.
3. Changed the site or the live path? Restart `killshot start` (the server loads Python
   code only at startup), run `killshot replay 372750 --speed 5` in a second terminal,
   and watch http://localhost:8000/games. Reload the page once after starting a replay.
4. For screenshots, Playwright with an iPhone device in light and dark mode, checking
   for horizontal overflow and console errors.

Tool versions: Node 26 (`.tool-versions` for asdf, `web/.nvmrc`), Python 3.11+, Postgres 16.
`web/.npmrc` pins the public npm registry (Colin's global `.npmrc` points at a work registry).
`npm run gen:api` uses TypeScript 5.9 through npx because TypeScript 7 has no compiler API.

## How it fits together

- **Data:** CollegeBasketballData.com (CBBD, Tier 2) for everything stored. CBBD has
  **no live play-by-play for basketball** (plays appear 30+ minutes after the final;
  tested twice), so during games the worker reads **ESPN's** free summary every 30 s.
  ESPN data is never stored as history; CBBD's record replaces it after the final.
- **Code path:** `sources/cbbd.py` and `sources/espn.py` translate provider data into our
  `Play` format (`plays.py`); nothing else knows provider field names. `stints.py`,
  `events.py`, `rollup.py`, `box.py` do the basketball math. `detail.py` builds a game
  page for both finished and live games. `live.py` builds the live page from ESPN.
- **Worker** (`worker.py`): schedule sync every 10 min around games / 6 h otherwise;
  fetches CBBD plays after the final with retries (5/10/20/40/60 min); from 10 min before
  tip, polls ESPN every 30 s into `live_state`; when CBBD's plays arrive, compares finals
  by team, logs `live check: ...`, deletes the live row. Stays inside the monthly CBBD budget.
- **API** (`api.py`, FastAPI): response shapes in `schemas.py`; the site's TypeScript
  types are generated from them. Serves the built site from `web/dist`.
- **Site** (`web/`): React 19, React Router, TanStack Query, Recharts, Tailwind 4, Vite.
  Game page and live score bar refresh every 30 s while live or around tip time.
- **Database:** Postgres, plain SQL in `db.py`, numbered migrations in `migrations/`
  (`004_...` next is `005_...`; a test enforces no gaps). Stored home/away-neutral
  and team-agnostic; only Kansas (CBBD team id `131`) is tracked.
- **Deploy:** Railway, one service from the `Dockerfile` running `killshot serve`
  (site + worker), plus Railway Postgres. Auto-deploys on push to `main`; health check
  `/healthz` fails if the worker heartbeat is over 30 min old.
- **Decisions** and their reasons: `docs/decisions.md` (30 so far). Add one when a
  choice would surprise someone later.

## Data quirks that bite

- CBBD and ESPN label every free throw "MadeFreeThrow", even misses: use `scoringPlay`.
- ESPN never lists who is on the floor; lineups are rebuilt from substitutions
  (`substitutions.py`). They match CBBD's listed lineups within about a minute per player.
- At neutral sites ESPN and CBBD can disagree on home and away: match teams by name.
- CBBD and ESPN win probability models differ (WVU 11/18: ESPN had KU 71% at tip, CBBD 36%).
- CBBD lists unknown opponents as a team named "TBD"; `startTimeTbd` marks placeholder tips.
- Some CBBD games have incomplete on-floor lists or no win probability.
- Lineup ratings use our own possession formula (FGA − ORB + TOV + 0.475·FTA,
  averaged over both teams), not CBBD's lineup endpoint.

## Practicalities

- Never put API keys in code, commits, or chat. The CBBD key lives in `.env` locally and
  in Railway's Variables (`CBBD_API_KEY`, spelled C-B-B-D).
- `gh pr create` may fail with a GraphQL error in some environments; the REST API
  works: `gh api repos/ColinGarner/killshot/pulls -X POST -f title=... -f head=... -f base=main -F body=@file`.
- Test fixtures (`tests/fixtures/`) are real gzipped CBBD and ESPN responses for KU's
  first games of 2026-27; the Kentucky game (`372750`, ESPN `401909786`) is the usual example.

## What's next

- 7.6: phone polish and Add to Home Screen (manifest, icons, safe areas).
- Small fixes: worker log says "next pass in 0 min" for 30 s waits; `killshot serve`'s
  missing-setting message mentions `.env`, which doesn't exist on Railway.
- Later: foul-trouble tracking, garbage-time toggle refinements, scouting the next opponent.
- If CBBD adds live basketball play-by-play, switch the worker's live polling from ESPN to
  CBBD (only `worker.py`'s fetch and `live.py`'s input change).
