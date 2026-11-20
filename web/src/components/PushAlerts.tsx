import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import { getSubscription, subscribe, supported, unsubscribe } from "../lib/push";

type Status = "unsupported" | "checking" | "off" | "on" | "busy" | "denied";

/**
 * A bell that turns killshot push alerts on or off: a notification whenever a
 * 10+ point run (by either team) shows up in a live game. Hidden entirely
 * where the browser can't support it (see lib/push.ts).
 */
export function PushAlerts() {
  const [status, setStatus] = useState<Status>(supported() ? "checking" : "unsupported");

  useEffect(() => {
    if (!supported()) return;
    getSubscription()
      .then((sub) => setStatus(sub ? "on" : "off"))
      .catch(() => setStatus("off"));
  }, []);

  if (status === "unsupported") return null;

  async function toggle() {
    setStatus("busy");
    try {
      if (status === "on") {
        const sub = await getSubscription();
        if (sub) await unsubscribe(sub);
        setStatus("off");
      } else {
        const { public_key } = await unwrap(api.GET("/api/push/vapid-key"));
        if (!public_key) throw new Error("not configured");
        await subscribe(public_key);
        setStatus("on");
      }
    } catch (e) {
      setStatus(e instanceof Error && e.message === "blocked" ? "denied" : "off");
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={status === "checking" || status === "busy"}
      aria-pressed={status === "on"}
      title={status === "denied" ? "Notifications are blocked in this browser" : "Get a notification for every killshot"}
      className={`flex min-h-11 shrink-0 items-center rounded-full border px-3 font-display text-[11px] font-bold tracking-widest uppercase ${
        status === "on" ? "border-white bg-white/15 text-white" : "border-white/40 text-white/80"
      }`}
    >
      {status === "on" ? "Alerts on" : status === "denied" ? "Blocked" : "Killshot alerts"}
    </button>
  );
}
