import { useEffect, useState } from "react";
import type { GameDetail, Player } from "../api/client";
import { clockTime, currentRun, isStale } from "../lib/live";

/** Re-render every 15 seconds, so "Updated" turns amber on time even if no new data arrives. */
function useNow(everyMs = 15_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(id);
  }, [everyMs]);
  return now;
}

/**
 * The live score bar: stays at the top of the screen while a game is on.
 * Score, ESPN's clock, our win probability, a flag during a 10-0 run, and how fresh the data is.
 */
export function LiveBar({ detail, team }: { detail: GameDetail; team: string }) {
  const now = useNow();
  const { game: g, live, win_prob } = detail;
  if (!live) return null;
  const final = g.state === "post";
  const winProb = win_prob.length ? win_prob[win_prob.length - 1].win_prob : null;
  const run = final ? null : currentRun(win_prob);
  const stale = !final && isStale(live.updated_at, now);

  return (
    <div className="sticky top-0 z-10 -mx-4 border-b border-slate-200 bg-white/95 px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-3 tabular-nums">
          <span className="font-display text-xs font-bold tracking-widest text-ku-crimson uppercase dark:text-ku-rose">
            {final ? "Final" : "● Live"}
          </span>
          <span className="font-display text-3xl font-bold">
            {g.pts ?? 0}-{g.opp_pts ?? 0}
          </span>
          <span className="text-sm text-slate-500">{final ? "" : g.status}</span>
        </div>
        {winProb !== null && (
          <div className="text-right">
            <div className="font-display text-2xl leading-none font-bold text-ku-blue tabular-nums dark:text-ku-sky">
              {Math.round(winProb)}%
            </div>
            <div className="text-[11px] text-slate-500 uppercase">{team} win</div>
          </div>
        )}
      </div>
      <div className="mt-1 flex items-center justify-between gap-3 text-xs">
        {run && run.pts >= 8 ? (
          <span
            className={`rounded px-1.5 py-0.5 font-bold text-white ${run.by === "team" ? "bg-ku-blue" : "bg-ku-crimson"}`}
          >
            {run.by === "team" ? team : g.opponent.name} on a {run.pts}-0 run
          </span>
        ) : (
          <span />
        )}
        <span className={stale ? "font-semibold text-amber-600 dark:text-amber-400" : "text-slate-500"}>
          {final ? "Official stats after the final is published" : `Updated ${clockTime(live.updated_at)}`}
          {stale && " · waiting for new data"}
        </span>
      </div>
    </div>
  );
}

/** Who is on the floor right now. A pill opens the player's season stats
 * (see PlayerModal) when `onSelectPlayer` is given. */
export function OnFloor({ detail, onSelectPlayer }: { detail: GameDetail; onSelectPlayer?: (player: Player) => void }) {
  const five = detail.live?.on_floor ?? [];
  if (!five.length || detail.game.state === "post") return null;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="On the floor">
      {[...five]
        .sort((a, b) => a.short_name.localeCompare(b.short_name))
        .map((p) => (
          <li key={p.id}>
            {onSelectPlayer ? (
              <button
                type="button"
                title={p.name}
                onClick={() => onSelectPlayer(p)}
                className="rounded-full border border-ku-blue/30 bg-ku-blue/5 px-3 py-1 text-sm font-semibold hover:bg-ku-blue/10 dark:border-ku-sky/30 dark:bg-ku-sky/10 dark:hover:bg-ku-sky/20"
              >
                {p.short_name}
              </button>
            ) : (
              <span
                title={p.name}
                className="block rounded-full border border-ku-blue/30 bg-ku-blue/5 px-3 py-1 text-sm font-semibold dark:border-ku-sky/30 dark:bg-ku-sky/10"
              >
                {p.short_name}
              </span>
            )}
          </li>
        ))}
    </ul>
  );
}
