"""Work out who was on the floor from substitutions, where the data doesn't say.

Some games arrive with incomplete on-floor lists: CBBD sometimes lists nobody
at tip-off and only adds players as they sub in, or briefly lists six. (ESPN's
live feed, read by `sources/espn.py`, never lists the floor at all.) This module
fills those gaps with two basketball facts:

1. Nobody can enter the game without subbing in. So anyone who does something
   (shoots, rebounds, fouls) or subs *out* before subbing in during a period
   must have started that period.
2. After that, the five only change at substitutions.

Plays that already list exactly five players for a team are trusted as they
are; this only fills in the rest.
"""
from . import plays as P


def _period_starters(period_plays: list[P.Play], team_id: str, previous: list[str]) -> list[str]:
    """The five who started a period (rule 1), topped up from whoever ended the
    previous period if fewer than five can be identified."""
    for play in period_plays:  # the data may already tell us, before this team's first sub
        if play.kind == P.SUB and play.team_id == team_id:
            break  # from here on, a complete list isn't necessarily the starting five
        five = play.on_floor.get(team_id, ())
        if len(five) == 5:
            return list(five)

    subbed_in: set[str] = set()
    starters: list[str] = []
    for play in period_plays:
        if play.team_id != team_id or not play.player_id:
            continue
        pid = play.player_id
        if play.kind == P.SUB and play.sub == "in":
            subbed_in.add(pid)
        elif pid not in subbed_in and pid not in starters:
            starters.append(pid)  # acted, or subbed out, before subbing in
        if len(starters) == 5:
            return starters
    for pid in previous:
        if len(starters) == 5:
            break
        if pid not in starters and pid not in subbed_in:
            starters.append(pid)
    return starters


def fill_lineups(plays: list[P.Play], team_ids: list[str]) -> int:
    """Fill in every play's on-floor list where it doesn't have exactly five
    players for a team, by replaying substitutions. Changes the plays in place.

    Returns how many (play, team) lists were filled in, so callers can report it.
    """
    filled = 0
    for team_id in team_ids:
        if all(len(p.on_floor.get(team_id, ())) == 5 for p in plays):
            continue  # nothing to fill for this team
        on: list[str] = []
        periods = sorted({p.period for p in plays})
        for period in periods:
            period_plays = [p for p in plays if p.period == period]
            on = _period_starters(period_plays, team_id, on)
            for play in period_plays:
                if play.team_id == team_id and play.kind == P.SUB and play.player_id:
                    if play.sub == "in" and play.player_id not in on:
                        on.append(play.player_id)
                    elif play.sub == "out" and play.player_id in on:
                        on.remove(play.player_id)
                listed = play.on_floor.get(team_id, ())
                if len(listed) == 5:
                    on = list(listed)  # trust a complete list, and carry on from it
                elif len(on) == 5:
                    play.on_floor[team_id] = tuple(sorted(on))
                    filled += 1
        filled += _fill_mid_batch(plays, team_id)
    return filled


def _fill_mid_batch(plays: list[P.Play], team_id: str) -> int:
    """Plays still without five are in the middle of a batch of subs at one
    moment (e.g. a free throw logged between two subs). The batch all happens
    at a dead ball, so use the complete five from the end of that same moment,
    or failing that, the last complete five before it."""
    filled = 0
    last_complete: tuple[str, ...] = ()
    for i, play in enumerate(plays):
        listed = play.on_floor.get(team_id, ())
        if len(listed) == 5:
            last_complete = listed
            continue
        end_of_moment: tuple[str, ...] = ()
        for later in plays[i + 1:]:
            if later.t != play.t or later.period != play.period:
                break
            if len(later.on_floor.get(team_id, ())) == 5:
                end_of_moment = later.on_floor[team_id]
        choice = end_of_moment or last_complete
        if len(choice) == 5:
            play.on_floor[team_id] = choice
            filled += 1
    return filled
