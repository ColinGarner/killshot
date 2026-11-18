import type { Lineup } from "../api/client";
import { lineupLabel, signed } from "../lib/format";

/** Five-man units with their minutes, possessions, plus-minus and net rating. */
export function LineupTable({ lineups, empty }: { lineups: Lineup[]; empty: string }) {
  if (lineups.length === 0) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full text-sm tabular-nums">
        <thead>
          <tr className="border-b-2 border-ku-blue font-display text-xs tracking-wider text-slate-500 uppercase dark:border-ku-sky">
            <th className="py-1.5 pr-3 text-left">Lineup</th>
            <th className="px-2 text-right">Min</th>
            <th className="px-2 text-right">Poss</th>
            <th className="px-2 text-right">+/−</th>
            <th className="pl-2 text-right">Net</th>
          </tr>
        </thead>
        <tbody>
          {lineups.map((l) => (
            <tr key={l.players.map((p) => p.id).join(",")} className="border-b border-slate-200 dark:border-slate-800">
              <td className="py-2 pr-3" title={l.players.map((p) => p.name).join(", ")}>
                {lineupLabel(l.players)}
              </td>
              <td className="px-2 text-right">{l.minutes.toFixed(1)}</td>
              <td className="px-2 text-right">{l.poss.toFixed(0)}</td>
              <td className={`px-2 text-right ${tone(l.plus_minus)}`}>{signed(l.plus_minus, 0)}</td>
              <td className={`pl-2 text-right font-semibold ${tone(l.net)}`}>{signed(l.net)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** KU blue for good, crimson for bad. */
export function tone(value: number): string {
  if (value > 0) return "text-ku-blue dark:text-ku-sky";
  if (value < 0) return "text-ku-crimson dark:text-ku-rose";
  return "";
}
