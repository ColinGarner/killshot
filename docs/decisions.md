# Decisions

Short records of choices that shaped the code, newest last. Each says what we
decided, why, and what we gave up.

## 1. The core library uses only the Python standard library
**Decided:** `killshot/` (ESPN client, stints, ratings) has no third-party dependencies.
**Why:** It's the part most worth reading and testing. Keeping it plain means it
runs anywhere with `python3`, and the database and web layers (later milestones)
depend on it, never the other way around.
**Gave up:** `requests`/`httpx` niceties in the ESPN client. `urllib` is enough.

## 2. Store everything from the home team's side, not "KU vs. opponent"
**Decided:** Games, win probability and killshots are recorded as home/away.
Stints are recorded per team, for both teams in every game. A page asks for one
team's view and the code flips it (`WinProbPoint.for_team`).
**Why:** We ship Kansas only, but the schema should work for any team (see the
plan's scope notes). Every game file already contains the opponent's lineups,
so keeping them is free and enables scouting later.
**Gave up:** Slightly less obvious code than `ku_pts` / `opp_pts`.

## 3. Stints are time ranges, and garbage time splits them
**Decided:** A stint is a continuous stretch with the same five on the floor,
with a start and end time. A new stint also starts when the margin crosses 20
in the second half or overtime, so every stint is either fully garbage time or
not at all.
**Why:** The proof of concept summed by lineup and lost the timing, which made a
garbage-time filter impossible. With time ranges, filtering is a `WHERE`.
**Gave up:** More rows (about 30 per team per game instead of about 15).

## 4. Possessions use the 0.475 free-throw weight
**Decided:** possessions = FGA − ORB + TOV + 0.475 × FTA, averaged across both teams.
**Why:** It's the standard college estimate (the NBA uses 0.44) and matches the
ratings on the proof-of-concept dashboard, which the tests pin.

## 5. Free throws belong to the five on the floor when they're shot
**Decided:** A substitution between free throws moves the second free throw to
the new lineup.
**Why:** It's what the play-by-play order says, and it keeps stint points
summing exactly to the final score. Some sites credit free throws to the
lineup on the floor at the time of the foul instead; the difference is tiny.

## 6. Postgres with plain SQL, no ORM
**Decided:** The schema is numbered `.sql` files in `migrations/`, applied in
order by a 20-line runner (`db.migrate`). Queries are hand-written SQL in
`killshot/db.py`, sent with psycopg (the standard Postgres driver for Python).
**Why:** Six tables don't need an ORM. The schema reads top to bottom in one
file, any query can be pasted into `psql`, and Railway's Postgres works the same.
**Gave up:** Auto-generated migrations. A schema change means writing
`002_something.sql` by hand.

## 7. Season numbers are calculated on request, not stored
**Decided:** No season tables yet. Season lineups and on/off splits are summed
from `stints` when asked for.
**Why:** A season is about 1,000 stints per team; adding them up takes
milliseconds. Stored rollups would need to be kept in sync after every game.
**Revisit when:** a page gets slow, or we track many teams.

## 8. Columns for stats, not JSON
**Decided:** Each stint has 20 plain integer columns (`team_pts`, `opp_fga`, ...)
instead of one JSON blob per side.
**Why:** So SQL can add them up directly:
`SELECT sum(team_pts) FROM stints WHERE team_id = '2305'`.

## 9. Known reconstruction problems are flagged, not hidden
**Decided:** The loader prints a warning for any game where rebuilt points don't
match the final score or a player's minutes are off by more than 1.5.
**Known cases (2025-26):** at Duke (one player off by 3.3 minutes) and Houston
at Kansas (15 seconds with the wrong number of players, losing one KU point).
Both come from gaps in ESPN's substitution data.

## 10. Migrations are forward-only, locked, and never edited after they run
**Decided:** Schema changes are new numbered files only (rules in
`migrations/README.md`). A migration run is one transaction holding a Postgres
advisory lock. A test requires file numbers to be 001, 002, 003... with no
gaps or repeats.
**Why:** On Railway, the web service and the worker can both start at once.
Without the lock, two simultaneous runs crashed trying to create the same
table (reproduced while building this). Editing an applied file would leave
local and production databases silently different.
**Gave up:** Undo ("down") migrations. Reversals are new forward files.

## 11. CollegeBasketballData.com is the only data source
**Decided:** All data (history, finals, schedule and, later, live) comes from
CollegeBasketballData.com (CBBD) on Tier 1 ($1/month, 5,000 calls). ESPN's
undocumented API is gone from the code.
**Why:** A documented, paid API is more dependable than ESPN's and is fine to
build a site on. CBBD lists the ten players on the floor with every play and
includes win probability, so lineups no longer have to be rebuilt from
substitutions. One source means one set of ids and nothing to keep in sync.
**Gave up:** ESPN's win-probability model (CBBD has its own) and ESPN as a
backup. If CBBD's play-by-play turns out not to update during games, the Live
tab shows score and clock only until the final; we'll decide then.

## 12. Our ratings math, not CBBD's lineup ratings
**Decided:** We build stints and ratings ourselves from CBBD's plays, and don't
use CBBD's `/lineups` ratings.
**Why:** CBBD counts possessions separately for each team, which can come out
very uneven. For KU's starting five vs. Kentucky it credits KU with 26
possessions and Kentucky with 38 over the same 17 minutes, which makes the net
rating +63.4. Teams alternate possessions, so we average both sides' estimates
(decision 4): +26.6 on ESPN data, +20.8 on CBBD's plays.

## 13. Provider quirks stay in the translator
**Decided:** `sources/cbbd.py` turns CBBD plays into our own `Play` format
(`killshot/plays.py`). Stints and events read only `Play` objects.
**Quirks handled there:** every free throw is labeled `MadeFreeThrow`, even
misses (we use `scoringPlay`); the on-floor list names teams but not team ids.
**Why:** A CBBD format change touches one file, and the basketball code stays
readable without provider vocabulary.

## 14. Win probability is optional
**Decided:** A game without win probability loads normally, with an empty chart
and `has_win_prob = False`; the loader flags it.
**Why:** CBBD has none for 9 of KU's 35 games in 2025-26, mostly February and
March (e.g. Houston at Kansas, the St. John's tournament game).

## 15. Incomplete CBBD lineups are filled in from substitutions
**Decided:** Where CBBD doesn't list exactly five players for a team, we fill the
list in (`killshot/substitutions.py`): the starters are whoever acts or subs out
before subbing in, then substitutions are replayed. A play caught mid-batch (a
free throw logged between two subs at one moment) takes the five from the end of
that moment. Complete CBBD lists are always trusted as they are.
**Found in 2025-26:** the first two games (Green Bay, at North Carolina) list
nobody at tip-off and add players only as they sub in; at Texas Tech and TCU,
CBBD briefly lists six. Before this fix those games lost up to 9 minutes of
lineups and some points. After it, all 39 stored games add up exactly for both
teams, and 2025-26 team net is back to +8.8.
**Also used for:** ESPN's live feed in Milestone 7, which never lists the floor.
**Limit:** in a test that erases KU's lists from the Kentucky game and rebuilds
them, every player's minutes come back within 30 seconds (CBBD sometimes
switches its list a play after the logged substitution).

## 16. Count every CBBD call
**Decided:** Each request adds one to `api_usage` for the current month. The
loader prints the total. Slowing live polling as the limit approaches comes
with the worker (Milestone 3).

## 17. Reprocess from stored raw data after logic changes
**Decided:** `python -m killshot.reprocess` rebuilds every stored game from
`games.raw` with the current code. It makes no API calls.
**Why:** Fixes like decision 15 change past results. Re-reading what we already
stored is instant, free, and doesn't depend on CBBD still serving old games.
