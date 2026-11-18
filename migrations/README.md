# Migrations

Each `.sql` file here changes the database schema. `killshot.db.migrate()` runs
any file that hasn't run yet, in number order, and records its name in the
`schema_migrations` table.

## Adding a change

Create the next number with a short description, e.g. `002_fouls.sql`:

```sql
-- 002: fouls, for foul-trouble tracking.
CREATE TABLE fouls ( ... );
```

Changing an existing table works the same way, with a new file:

```sql
-- 003: conference games, for a Big 12-only filter.
ALTER TABLE games ADD COLUMN conf_game boolean NOT NULL DEFAULT false;
```

## Rules

1. **Never edit a file that has already run anywhere** (your machine, CI, Railway).
   The runner only checks file names, so an edited file never re-runs and the
   databases silently drift apart. Fix mistakes with a new file.
2. **No undo files.** To reverse a change, write a new forward migration.
3. **Keep changes safe for the code that's already running.** Migrations run
   just before new code starts. Adding tables or nullable columns is always safe;
   renaming or dropping a column takes two releases (stop using it, then drop it).
4. **Numbers are unique and have no gaps** (001, 002, 003, ...). If two branches
   both add `002`, the second to merge renumbers. A test enforces this.

## Safety built in

- A run happens in one transaction: if any file fails, none of the run is kept.
- A Postgres advisory lock means two processes migrating at the same moment
  (the web service and the worker) take turns instead of colliding.
