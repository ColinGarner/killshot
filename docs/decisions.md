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
