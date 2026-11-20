"""Push notifications fire for a new killshot in a live game.

Uses the Kentucky ESPN fixture (one 12-0 Kansas run, same one test_live.py and
test_game_events.py check), so `new_runs` is tested against a real game
instead of a hand-built one.
"""
from killshot import push
from test_live import page_after


def test_a_new_killshot_is_the_one_that_wasnt_there_before():
    before, after = page_after(0), page_after()
    (run,) = push.new_runs(before, after)
    assert (run["by"], run["label"]) == ("team", "12-0")


def test_nothing_is_new_on_a_games_first_poll():
    assert push.new_runs(None, page_after()) == []  # None: nothing to compare against yet


def test_nothing_is_new_once_a_killshot_has_already_been_seen():
    after = page_after()
    assert push.new_runs(after, after) == []


def test_killshot_message_for_our_own_run():
    run = {"by": "team", "label": "12-0", "score_after": [63, 41]}
    title, body = push.killshot_message("Kansas", "Kentucky", run)
    assert title == "Killshot: Kansas 12-0"
    assert body == "Kansas 63, Kentucky 41, after a 12-0 run."


def test_killshot_message_for_the_opponents_run():
    run = {"by": "opponent", "label": "10-0", "score_after": [50, 55]}
    title, body = push.killshot_message("Kansas", "Kentucky", run)
    assert title == "Killshot: Kentucky 10-0"
    assert body == "Kentucky 55, Kansas 50, after a 10-0 run."


def test_notify_logs_the_killshot_but_sends_nothing_without_a_vapid_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    # conn is never touched: send() bails out before it's needed.
    notes = push.notify_new_killshots(None, page_after(0), page_after(), "Kansas")
    assert notes == ["push: Killshot: Kansas 12-0"]


def test_notify_does_nothing_when_there_is_no_new_killshot(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    after = page_after()
    assert push.notify_new_killshots(None, after, after, "Kansas") == []


def test_send_does_nothing_without_a_vapid_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert push.send(None, "title", "body") == []


def test_a_successful_send_is_logged_too_not_just_failures(monkeypatch):
    # Otherwise "no notification showed up" and "nothing was sent" look identical in the log.
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "not-used-webpush-is-stubbed")
    monkeypatch.setattr(push.db, "push_subscriptions", lambda conn: [
        {"endpoint": "e1", "p256dh": "p", "auth": "a"}, {"endpoint": "e2", "p256dh": "p", "auth": "a"}])
    monkeypatch.setattr(push, "webpush", lambda **kwargs: None)
    assert push.send(None, "title", "body") == ["push: sent to 2 subscribers"]


def test_a_network_failure_sending_to_one_subscription_is_logged_not_raised(monkeypatch):
    # A DNS or connection error raises a plain exception, not WebPushException --
    # it must be caught too, or one bad subscription would crash the worker.
    def boom(**kwargs):
        raise ConnectionError("down")

    monkeypatch.setenv("VAPID_PRIVATE_KEY", "not-used-webpush-is-stubbed")
    monkeypatch.setattr(push.db, "push_subscriptions", lambda conn: [{"endpoint": "e1", "p256dh": "p", "auth": "a"}])
    monkeypatch.setattr(push, "webpush", boom)
    assert push.send(None, "title", "body") == ["push: failed (ConnectionError('down'))"]
