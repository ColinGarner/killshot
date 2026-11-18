// Small helpers for the live game page.
import type { WinProbPoint } from "../api/client";

/** How long without new data before the "Updated" stamp turns amber. */
export const STALE_AFTER_MS = 2 * 60 * 1000;

/** How often the page asks for new data while a game is on (the worker reads ESPN this often). */
export const LIVE_REFRESH_MS = 30 * 1000;

/** "8:42 PM", in Kansas time. */
export function clockTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" }).format(
    new Date(iso),
  );
}

/**
 * Around a game's scheduled time (15 minutes before tip to 4 hours after), pages keep
 * checking for updates even before the game goes live, so it switches to live by itself.
 */
export function isGameTime(startAt: string, now: number = Date.now()): boolean {
  const tip = new Date(startAt).getTime();
  return now >= tip - 15 * 60 * 1000 && now <= tip + 4 * 60 * 60 * 1000;
}

/** True when the live data is older than STALE_AFTER_MS. */
export function isStale(updatedAt: string, now: number = Date.now()): boolean {
  return now - new Date(updatedAt).getTime() > STALE_AFTER_MS;
}

/**
 * The run going on right now: points one team has scored since the other's last
 * basket. `null` before anyone scores, or when both scored in the same moment.
 * Points are sampled every 10 game-seconds, which is plenty for a 10-0 run.
 */
export function currentRun(points: WinProbPoint[]): { by: "team" | "opponent"; pts: number } | null {
  if (points.length === 0) return null;
  const last = points[points.length - 1];
  // The last sample before each team's most recent score (-1: they haven't scored since tip).
  const lastChange = (score: (p: WinProbPoint) => number) =>
    points.findLastIndex((p) => score(p) !== score(last));
  const ours = lastChange((p) => p.pts);
  const theirs = lastChange((p) => p.opp_pts);
  if (ours === theirs) return null; // nobody has scored, or both did in the same moment
  if (ours > theirs) {
    // We scored most recently: count our points since their last basket.
    const since = theirs >= 0 ? points[theirs + 1].pts : 0;
    return { by: "team", pts: last.pts - since };
  }
  const since = ours >= 0 ? points[ours + 1].opp_pts : 0;
  return { by: "opponent", pts: last.opp_pts - since };
}
