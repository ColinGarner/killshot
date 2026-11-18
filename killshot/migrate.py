"""Apply any database migrations that haven't run yet, then exit.

    python -m killshot.migrate

The web service runs this before starting (locally and on Railway). The worker
also migrates at startup; the migration lock makes it safe for both to try.
"""
import os

from . import db


def main() -> None:
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        applied = db.migrate(conn)
    print(f"migrations applied: {', '.join(applied)}" if applied else "database is up to date")


if __name__ == "__main__":
    main()
