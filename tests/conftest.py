import gzip
import json
import os
from pathlib import Path

import pytest

from killshot import db
from killshot.game import Game
from killshot.sources import cbbd

FIXTURES = Path(__file__).parent / "fixtures"

# CBBD team ids
KANSAS, KENTUCKY_TEAM = "131", "135"

# KU's first four 2026-27 games, saved from CollegeBasketballData.com (CBBD game ids).
FORDHAM, MTSU, KENTUCKY, UNLV = "372645", "372703", "372750", "372836"


def load_data(game_id: str) -> dict:
    """CBBD's game record and plays, as `cbbd.Client.game_data` returns them."""
    with gzip.open(FIXTURES / f"cbbd_{game_id}.json.gz", "rt") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def games() -> dict[str, Game]:
    return {g: cbbd.to_game(load_data(g)) for g in (FORDHAM, MTSU, KENTUCKY, UNLV)}


@pytest.fixture()
def conn():
    """A fresh, fully migrated database. Needs TEST_DATABASE_URL pointing at a
    throwaway database: every table is dropped and recreated."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    with db.connect(url) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        db.migrate(c)
        yield c
