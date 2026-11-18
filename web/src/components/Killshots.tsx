import type { Killshot } from "../api/client";

/** Every run of 10+ unanswered points, by either team. */
export function Killshots({ killshots, opponent }: { killshots: Killshot[]; opponent: string }) {
  if (killshots.length === 0) {
    return <p className="text-sm text-slate-500">No 10-0 runs by either team.</p>;
  }
  return (
    <ul className="divide-y divide-slate-200 dark:divide-slate-800">
      {killshots.map((k) => (
        <li key={`${k.t0}-${k.t1}`} className="flex flex-wrap items-baseline gap-x-3 py-2 text-sm">
          <span className={`font-display text-lg font-bold ${k.by === "team" ? "text-ku-blue dark:text-ku-sky" : "text-ku-crimson dark:text-ku-rose"}`}>
            {k.label}
          </span>
          <span className="font-semibold">{k.by === "team" ? "Kansas" : opponent}</span>
          <span className="text-slate-500">
            {k.start} to {k.end}
          </span>
          <span className="tabular-nums text-slate-500">
            {k.score_before.join("-")} → {k.score_after.join("-")}
          </span>
        </li>
      ))}
    </ul>
  );
}
