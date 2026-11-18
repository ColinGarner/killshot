"""ESPN's play format is translated into ours correctly, and a game built from
ESPN tells the same story as CBBD's official record of it.

Fixtures: ESPN's summaries of KU vs Kentucky and UNLV, trimmed to the parts we
read (header, box score, plays, win probability).
"""
import copy
import gzip
import json

import pytest

from killshot import plays as P
from killshot.sources import cbbd, espn
from conftest import FIXTURES, KENTUCKY, UNLV, load_data

# ESPN event ids of the same games; CBBD's record lists them as sourceId.
ESPN_IDS = {KENTUCKY: "401909786", UNLV: "401909787"}
KANSAS_ESPN = "2305"


def load_espn(event_id: str) -> dict:
    with gzip.open(FIXTURES / f"espn_{event_id}.json.gz", "rt") as f:
        return json.load(f)


def kansas(game):
    """The Kansas side of a game, by name: ESPN and CBBD don't always agree on home and away."""
    return next(t for t in (game.home, game.away) if t.name == "Kansas")


@pytest.fixture(scope="module", params=[KENTUCKY, UNLV])
def both(request):
    """(CBBD's game, ESPN's game) for the same night."""
    cbbd_game = cbbd.to_game(load_data(request.param))
    assert cbbd_game.espn_id == ESPN_IDS[request.param]
    return cbbd_game, espn.to_game(load_espn(cbbd_game.espn_id))


# --- single plays ------------------------------------------------------------

def raw_plays():
    return load_espn(ESPN_IDS[UNLV])["plays"]


def test_a_missed_free_throw_is_an_attempt_not_a_make():
    # Like CBBD, ESPN labels missed free throws "MadeFreeThrow".
    missed = next(p for p in raw_plays() if p["type"]["text"] == "MadeFreeThrow" and not p["scoringPlay"])
    play = espn.to_play(missed, {})
    assert play.kind == P.FREE_THROW and not play.made and play.points == 0


def test_a_missed_three_is_a_three_worth_nothing():
    missed = next(p for p in raw_plays() if p.get("pointsAttempted") == 3 and not p["scoringPlay"])
    play = espn.to_play(missed, {})
    assert play.kind == P.SHOT and play.three and not play.made and play.points == 0


def test_substitutions_read_their_direction_from_the_text():
    subs = [espn.to_play(p, {}) for p in raw_plays() if p["type"]["text"] == "Substitution"]
    assert subs and {s.sub for s in subs} == {"in", "out"}


def test_time_counts_up_from_tip_off():
    plays = [espn.to_play(p, {}) for p in raw_plays()]
    assert plays[0].t == 0
    assert plays[-1].t == 2400  # end of regulation
    assert all(a.t <= b.t for a, b in zip(plays, plays[1:]))


# --- a whole game ------------------------------------------------------------

def test_lineups_are_rebuilt_for_every_play(both):
    _, game = both
    for team in (game.home, game.away):
        q = game.quality(team.id)
        assert q["invalid_seconds"] == 0
        assert q["points_match"], q["rebuilt_points"]


def test_rebuilt_minutes_match_espns_box_score(both):
    # The box score rounds to whole minutes, so allow 1.
    _, game = both
    box = load_espn(game.espn_id)["boxscore"]["players"]
    for team in box:
        minutes = game.minutes(team["team"]["id"])
        for a in team["statistics"][0]["athletes"]:
            listed = float(a["stats"][0]) if a["stats"] and a["stats"][0] not in ("", "--") else 0
            assert abs(minutes.get(a["athlete"]["id"], 0) - listed) <= 1, a["athlete"]["displayName"]


def test_espn_and_cbbd_agree_on_the_score_and_killshots(both):
    official, live = both
    assert (kansas(live).score, live.opponent(kansas(live).id).score) == \
           (kansas(official).score, official.opponent(kansas(official).id).score)
    assert [(r.pts, r.t0, r.t1) for r in live.runs] == [(r.pts, r.t0, r.t1) for r in official.runs]
    assert len(live.win_prob) == len(official.win_prob)


def test_espn_and_cbbd_minutes_differ_by_at_most_a_minute_and_a_half(both):
    # Live lineups are rebuilt from substitutions; CBBD's are listed. Close, not identical.
    official, live = both
    by_name = lambda g: {g.players[p].name: m for p, m in g.minutes(kansas(g).id).items()}
    a, b = by_name(official), by_name(live)
    assert max(abs(a.get(n, 0) - b.get(n, 0)) for n in a | b) <= 1.5


def test_at_neutral_sites_the_sources_can_disagree_on_home_and_away():
    # Why the final check matches teams by name, not by side.
    official = cbbd.to_game(load_data(KENTUCKY))
    live = espn.to_game(load_espn(ESPN_IDS[KENTUCKY]))
    assert official.home.name == "Kansas" and live.home.name == "Kentucky"
    assert kansas(live).id == KANSAS_ESPN


def test_a_game_in_progress_adds_up_so_far():
    # Cut the Kentucky game off midway through the 2nd half, as the live feed would show it.
    data = copy.deepcopy(load_espn(ESPN_IDS[KENTUCKY]))
    data["plays"] = data["plays"][:330]
    last = data["plays"][-1]
    data["header"]["competitions"][0]["status"]["type"].update(state="in", shortDetail="2nd half")
    for side in data["header"]["competitions"][0]["competitors"]:
        side["score"] = str(last["homeScore"] if side["homeAway"] == "home" else last["awayScore"])

    game = espn.to_game(data)
    assert game.state == "in"
    for team in (game.home, game.away):
        q = game.quality(team.id)
        assert q["points_match"] and q["invalid_seconds"] == 0
