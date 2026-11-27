"""The live game page: built from ESPN while a game is on.

    page = live.build(row, team_id, espn.to_game(espn.summary(event_id)))

`row` is our games-table row for the game (CBBD's ids, schedule and venue);
ESPN supplies everything that changes during the game: score, clock, lineups,
win probability and killshots. The result has the same shape as a finished
game's page, plus a `live` block (clock, who is on the floor, when it was read).

ESPN and CBBD can disagree on which team is home at a neutral site, so the two
are matched by team name, never by side.
"""
import copy
import datetime as dt

from . import detail
from .clock import label
from .game import Game, Team


def our_side(espn_game: Game, our_name: str, opponent_name: str) -> Team:
    """Which of ESPN's two teams is ours. By name, falling back to 'not the opponent'."""
    for team in (espn_game.home, espn_game.away):
        if team.name == our_name:
            return team
    for team in (espn_game.home, espn_game.away):
        if team.name == opponent_name:
            return espn_game.opponent(team.id)
    raise ValueError(f"ESPN's teams ({espn_game.home.name}, {espn_game.away.name}) "
                     f"don't match {our_name} vs {opponent_name}")


def build(row: dict, team_id: str, espn_game: Game, now: dt.datetime | None = None) -> dict:
    """The live game page for one team, from our games row and ESPN's game."""
    home_in_row = row["home_team_id"] == team_id
    our_name = row["home_name"] if home_in_row else row["away_name"]
    opponent_name = row["away_name"] if home_in_row else row["home_name"]
    us = our_side(espn_game, our_name, opponent_name)
    them = espn_game.opponent(us.id)

    summary = detail.game_summary(row, team_id)
    summary.update(live=True, state=espn_game.state, status=espn_game.status, pts=us.score, opp_pts=them.score,
                   result=("W" if us.score > them.score else "L") if espn_game.state == "post" else None)

    people = {pid: {"id": pid, "name": p.name, "short_name": p.short_name} for pid, p in espn_game.players.items()}
    stints = espn_game.stints.get(us.id, [])
    # ESPN's timelines are from ESPN's home side, so flip by ESPN's idea of home.
    box = [detail.team_box({"id": team_id, "name": our_name}, espn_game.box.get(us.id, []), people),
           detail.team_box(summary["opponent"], espn_game.box.get(them.id, []), people)]
    page = detail.build(summary, us.id, us.is_home, stints, espn_game.win_prob, espn_game.runs, people, box)

    last = stints[-1] if stints else None
    page["live"] = {
        "updated_at": (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
        "clock": label(last.t_end) if last else None,       # e.g. "2nd 12:41"
        "on_floor": [detail.player(people, p) for p in last.player_ids] if last and last.valid else [],
    }
    return page


def snapshot(summary: dict, n_plays: int) -> dict:
    """ESPN's summary as it would have looked after the first `n_plays` plays.
    Used by `killshot replay` and the tests to play back a finished game."""
    data = copy.deepcopy(summary)
    plays = data["plays"][:n_plays]
    data["plays"] = plays
    finished = n_plays >= len(summary["plays"])
    comp = data["header"]["competitions"][0]
    if not finished:
        last = plays[-1] if plays else {"homeScore": 0, "awayScore": 0}
        comp["status"]["type"].update(state="in", completed=False, description="In Progress",
                                      shortDetail=_clock_text(last))
        for side in comp["competitors"]:
            side["score"] = str(last["homeScore"] if side["homeAway"] == "home" else last["awayScore"])
    ids = {p["id"] for p in plays}
    data["winprobability"] = [w for w in data.get("winprobability") or [] if w["playId"] in ids]
    return data


def _clock_text(play: dict) -> str:
    if "period" not in play:
        return "Pregame"
    return f"{play['clock']['displayValue']} - {play['period']['displayValue']}"
