-- 005: push notifications.
--
-- A fan's browser subscribes once, through the Web Push API (see push.py and
-- web/src/lib/push.ts). The worker sends a push to every row here whenever a
-- new killshot shows up in a live game. endpoint is the subscription's own
-- unique id, assigned by the browser's push service; p256dh and auth are the
-- keys it gave us to encrypt each message.

CREATE TABLE push_subscriptions (
    endpoint    text PRIMARY KEY,
    p256dh      text NOT NULL,
    auth        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
