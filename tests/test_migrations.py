"""Migration files are well-formed, and running them is safe even when two
processes start at once."""
import os
import re
import threading

import pytest

from killshot import db

NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def test_migration_files_are_numbered_001_002_003_with_no_gaps_or_repeats():
    # Two branches that both add "002_..." must be renumbered before merging.
    names = [p.name for p in db.migration_files()]
    for name in names:
        assert NAME.match(name), f"{name} should look like 002_short_description.sql"
    numbers = [int(NAME.match(n).group(1)) for n in names]
    assert numbers == list(range(1, len(names) + 1)), f"expected 001..{len(names):03d}, got {names}"


URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")
def test_two_processes_migrating_at_once_apply_each_file_exactly_once():
    with db.connect(URL) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        c.commit()

    results, errors = [], []

    def run():
        try:
            with db.connect(URL) as c:
                results.append(db.migrate(c))
        except Exception as e:  # collected so the test can report it
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    all_files = [p.name for p in db.migration_files()]
    # One process applied everything; the other waited, then found nothing to do.
    assert sorted(results, key=len) == [[], all_files]
