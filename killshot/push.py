"""Web push notifications: sent whenever a new killshot shows up in a live game.

Called from `worker.py` while it polls ESPN, and from `replay.py` so a replay
exercises the same path for testing. A killshot only enters a live page's
`killshots` list once the run is over (the other team scores again, or the
game ends -- see events.killshots), so the push arrives then, not the instant
the run passes 10 points.

Settings (environment variables):
    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY   the site's push identity; generate a
                                           pair with `killshot vapid`
    VAPID_SUBJECT                         a mailto: or https: contact the push
                                           services can reach about this site
                                           (default: mailto:nobody@example.com)

With no VAPID_PRIVATE_KEY set, send() does nothing -- so tests and a fresh
checkout don't need push configured to run.
"""
import json
import os

import psycopg
from pywebpush import WebPushException, webpush

from . import db


def new_runs(prev_page: dict | None, page: dict) -> list[dict]:
    """The killshots in `page` that weren't in `prev_page` yet.

    `prev_page` is None on a game's first poll (nothing to compare against),
    so nothing counts as new -- a worker that starts mid-game, or a restart,
    never fires a pile of alerts for runs that already happened.
    """
    if prev_page is None:
        return []
    return page["killshots"][len(prev_page["killshots"]):]


def killshot_message(team_name: str, opponent_name: str, run: dict) -> tuple[str, str]:
    """(title, body) for a push about one closed-out killshot."""
    pts, opp_pts = run["score_after"]
    scorer = team_name if run["by"] == "team" else opponent_name
    title = f"Killshot: {scorer} {run['label']}"
    body = (f"{team_name} {pts}, {opponent_name} {opp_pts}, after a {run['label']} run."
            if run["by"] == "team" else
            f"{opponent_name} {opp_pts}, {team_name} {pts}, after a {run['label']} run.")
    return title, body


def notify_new_killshots(conn: psycopg.Connection, prev_page: dict | None, page: dict, team_name: str) -> list[str]:
    """Push a notification for every killshot `page` has that `prev_page` didn't.
    Returns a log line per killshot found (whether or not sending it worked)."""
    runs = new_runs(prev_page, page)
    if not runs:
        return []
    opponent_name = page["game"]["opponent"]["name"]
    notes = []
    for run in runs:
        title, body = killshot_message(team_name, opponent_name, run)
        notes.append(f"push: {title}")
        notes += send(conn, title, body, url=f"/games/{page['game']['id']}")
    return notes


def send(conn: psycopg.Connection, title: str, body: str, url: str = "/") -> list[str]:
    """Push one notification to every saved subscription.

    A subscription the browser has revoked (its push service answers 404 or
    410) is deleted; any other failure is only logged, so one bad subscription
    never stops the rest from being notified. Returns a log line per failure.
    """
    private_key = os.environ.get("VAPID_PRIVATE_KEY")
    if not private_key:
        return []
    payload = json.dumps({"title": title, "body": body, "url": url})
    claims = {"sub": os.environ.get("VAPID_SUBJECT", "mailto:nobody@example.com")}
    notes = []
    for sub in db.push_subscriptions(conn):
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"],
                                   "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=payload, vapid_private_key=private_key, vapid_claims=dict(claims))
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                db.delete_subscription(conn, sub["endpoint"])
                notes.append(f"push: subscription gone (endpoint ...{sub['endpoint'][-12:]}), removed")
            else:
                notes.append(f"push: failed ({e})")
        except Exception as e:  # a network hiccup must not stop the others, or whoever called this
            notes.append(f"push: failed ({e!r})")
    return notes
