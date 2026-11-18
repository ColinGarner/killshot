import type { OnOff } from "../api/client";
import { signed } from "../lib/format";
import { tone } from "./LineupTable";

/**
 * Each player's on/off split: the team's net rating with him on the floor minus
 * with him off. A bar shows the size and direction of the gap.
 */
export function OnOffTable({ rows }: { rows: OnOff[] }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">No players with enough minutes yet.</p>;
  const widest = Math.max(...rows.map((r) => Math.abs(r.on_off)), 1);
  return (
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full text-sm tabular-nums">
        <thead>
          <tr className="border-b-2 border-ku-blue font-display text-xs tracking-wider text-slate-500 uppercase dark:border-ku-sky">
            <th className="py-1.5 pr-3 text-left">Player</th>
            <th className="px-2 text-right">Min on</th>
            <th className="px-2 text-right">Net on</th>
            <th className="px-2 text-right">Net off</th>
            <th className="pl-2 text-right">On/off</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.player.id} className="border-b border-slate-200 dark:border-slate-800">
              <td className="py-2 pr-3 whitespace-nowrap" title={r.player.name}>
                {r.player.short_name}
              </td>
              <td className="px-2 text-right">{r.on.minutes.toFixed(0)}</td>
              <td className={`px-2 text-right ${tone(r.on.net)}`}>{signed(r.on.net)}</td>
              <td className={`px-2 text-right ${r.off ? tone(r.off.net) : ""}`}>{r.off ? signed(r.off.net) : "–"}</td>
              <td className="pl-2">
                <div className="flex items-center justify-end gap-2">
                  <span className="hidden h-2 w-16 sm:block" aria-hidden="true">
                    <span
                      className={`block h-2 rounded-sm ${r.on_off >= 0 ? "ml-auto bg-ku-blue dark:bg-ku-sky" : "bg-ku-crimson dark:bg-ku-rose"}`}
                      style={{ width: `${(Math.abs(r.on_off) / widest) * 100}%` }}
                    />
                  </span>
                  <span className={`w-14 text-right font-semibold ${tone(r.on_off)}`}>{signed(r.on_off)}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
