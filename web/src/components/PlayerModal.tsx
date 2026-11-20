import { useEffect } from "react";
import type { Player, PlayerAdvanced } from "../api/client";
import { signed } from "../lib/format";

/**
 * A player's season stats in a dismissable sheet: CollegeBasketballData's own numbers
 * (usage, efficiency ratings, shot-type detail), not this app's stint-based Ratings.
 * Closes on Escape, a backdrop click, or the × button.
 */
export function PlayerModal({
  player,
  advanced,
  onClose,
}: {
  player: Player;
  advanced: PlayerAdvanced | null | undefined;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${player.name}'s season stats`}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-xl sm:rounded-2xl dark:bg-slate-900"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h3 className="font-display text-xl font-bold">{player.name}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-m-2 flex size-9 shrink-0 items-center justify-center rounded-full text-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            ×
          </button>
        </div>
        {advanced ? <Stats advanced={advanced} /> : <p className="text-sm text-slate-500">No season stats synced yet.</p>}
      </div>
    </div>
  );
}

function Stats({ advanced: a }: { advanced: PlayerAdvanced }) {
  const perGame = (total: number) => (a.games ? (total / a.games).toFixed(1) : "0.0");
  const tiles: [string, string][] = [
    ["PPG", perGame(a.points)],
    ["RPG", perGame(a.rebounds.total)],
    ["APG", perGame(a.assists)],
    ["SPG", perGame(a.steals)],
    ["BPG", perGame(a.blocks)],
  ];
  const shooting: [string, { made: number; attempted: number; pct: number | null }][] = [
    ["FG", a.field_goals],
    ["3PT", a.three_point_field_goals],
    ["FT", a.free_throws],
  ];
  const advancedStats: [string, string][] = [
    ["Usage", pct(a.usage)],
    ["ORtg", num(a.offensive_rating)],
    ["DRtg", num(a.defensive_rating)],
    ["Net", a.net_rating != null ? signed(a.net_rating) : "–"],
    ["TS%", pct(a.true_shooting_pct != null ? a.true_shooting_pct * 100 : null)],
    ["eFG%", pct(a.effective_fg_pct)],
    ["PORPAG", num(a.porpag)],
    ["AST/TO", num(a.assists_turnover_ratio)],
    ["OREB%", pct(a.offensive_rebound_pct)],
    ["FT rate", pct(a.free_throw_rate)],
  ];

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">
        {a.starts}/{a.games} starts · {perGame(a.minutes)} min/game
      </p>

      <div className="grid grid-cols-5 gap-2 text-center">
        {tiles.map(([label, value]) => (
          <div key={label}>
            <div className="font-display text-xl font-bold text-ku-blue tabular-nums dark:text-ku-sky">{value}</div>
            <div className="text-[10px] tracking-wider text-slate-500 uppercase">{label}</div>
          </div>
        ))}
      </div>

      <table className="w-full text-sm tabular-nums">
        <tbody>
          {shooting.map(([label, s]) => (
            <tr key={label} className="border-b border-slate-200 dark:border-slate-800">
              <td className="py-1.5 pr-3 font-semibold">{label}</td>
              <td className="py-1.5 text-right text-slate-500">
                {s.made}-{s.attempted}
              </td>
              <td className="py-1.5 pl-3 text-right font-semibold">{pct(s.pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        {advancedStats.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-2">
            <span className="text-slate-500">{label}</span>
            <span className="font-semibold tabular-nums">{value}</span>
          </div>
        ))}
      </div>

      <p className="text-xs text-slate-500">
        Win shares: {num(a.win_shares.total)} ({num(a.win_shares.total_per_40)} per 40 minutes)
      </p>
    </div>
  );
}

function pct(value: number | null | undefined): string {
  return value == null ? "–" : `${value.toFixed(1)}%`;
}

function num(value: number | null | undefined): string {
  return value == null ? "–" : value.toFixed(1);
}
