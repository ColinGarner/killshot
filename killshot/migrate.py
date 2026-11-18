"""Create the database if needed and apply any migrations that haven't run yet.

    killshot migrate
"""
import os

from . import db


def main() -> None:
    url = os.environ["DATABASE_URL"]
    if db.ensure_database(url):
        print("created the database")
    with db.connect(url) as conn:
        applied = db.migrate(conn)
    print(f"migrations applied: {', '.join(applied)}" if applied else "database is up to date")


if __name__ == "__main__":
    main()
