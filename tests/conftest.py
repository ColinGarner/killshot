import gzip
import json
from pathlib import Path

import pytest

from killshot.game import Game

FIXTURES = Path(__file__).parent / "fixtures"
KANSAS = "2305"

# KU's first four 2026-27 games, saved from ESPN.
FORDHAM, MTSU, KENTUCKY, UNLV = "401909784", "401909785", "401909786", "401909787"


def load_summary(event_id: str) -> dict:
    with gzip.open(FIXTURES / f"{event_id}.json.gz", "rt") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def games() -> dict[str, Game]:
    return {e: Game.from_summary(load_summary(e)) for e in (FORDHAM, MTSU, KENTUCKY, UNLV)}
