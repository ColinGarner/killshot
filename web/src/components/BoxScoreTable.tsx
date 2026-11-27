import type { BoxLine, Player, TeamBox } from "../api/client";
import { signed } from "../lib/format";
import { tone } from "./LineupTable";

const madeOf = (made: number, tried: number) => `${made}-${tried}`;

/**
 * One team's box score: a row per player, most minutes first, and a team line.
 * The name column stays put while the numbers scroll sideways on a phone.
 * Names open season stats (PlayerModal) when `onSelectPlayer` is given.
 */
export function BoxScoreTable({ box, onSelectPlayer }: { box: TeamBox; onSelectPlayer?: (player: Player) => void }) {
  if (box.players.length === 0) return <p className="text-sm text-slate-500">No stats yet.</p>;
  const t = box.totals;
  const shared = sharedShortNames(box.players.map((l) => l.player));
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full text-sm whitespace-nowrap tabular-nums">
        <thead>
          <tr className="border-b-2 border-ku-blue font-display text-xs tracking-wider text-slate-500 uppercase dark:border-ku-sky">
            <th className={`${stickyCell} py-1.5 pr-3 text-left`}>Player</th>
            {["Min", "Pts", "FG", "3PT", "FT", "Reb", "OReb", "Ast", "Stl", "Blk", "TO", "PF", "+/−"].map((h) => (
              <th key={h} className={h === "+/−" ? "pr-4 pl-2 text-right" : "px-2 text-right"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {box.players.map((l) => (
            <tr key={l.player.id} className="border-b border-slate-200 dark:border-slate-800">
              <td className={`${stickyCell} py-2 pr-3`}>
                <Name player={l.player} label={displayName(l.player, shared)} onSelectPlayer={onSelectPlayer} />
              </td>
              <Numbers line={l} />
              <td className={`pr-4 pl-2 text-right ${tone(l.plus_minus)}`}>{signed(l.plus_minus, 0)}</td>
            </tr>
          ))}
          <tr className="font-semibold">
            <td className={`${stickyCell} py-2 pr-3`}>Team</td>
            <td className="px-2 text-right" />
            <Numbers line={t} />
            <td className="pr-4 pl-2" />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/** Pts through PF, shared by player rows and the team line (which has no minutes or +/-). */
function Numbers({ line: l }: { line: Omit<BoxLine, "player" | "minutes" | "plus_minus"> & { minutes?: number } }) {
  return (
    <>
      {l.minutes !== undefined && <td className="px-2 text-right">{Math.round(l.minutes)}</td>}
      <td className="px-2 text-right font-semibold">{l.pts}</td>
      <td className="px-2 text-right">{madeOf(l.fgm, l.fga)}</td>
      <td className="px-2 text-right">{madeOf(l.tpm, l.tpa)}</td>
      <td className="px-2 text-right">{madeOf(l.ftm, l.fta)}</td>
      <td className="px-2 text-right">{l.oreb + l.dreb}</td>
      <td className="px-2 text-right">{l.oreb}</td>
      <td className="px-2 text-right">{l.ast}</td>
      <td className="px-2 text-right">{l.stl}</td>
      <td className="px-2 text-right">{l.blk}</td>
      <td className="px-2 text-right">{l.tov}</td>
      <td className="px-2 text-right">{l.pf}</td>
    </>
  );
}

/** Short names used by more than one player on the team ("Williams" twice). */
export function sharedShortNames(players: Player[]): Set<string> {
  const seen = new Set<string>();
  const shared = new Set<string>();
  for (const p of players) (seen.has(p.short_name) ? shared : seen).add(p.short_name);
  return shared;
}

/** "Williams", or "M. Williams" when two players share it. */
export function displayName(player: Player, shared: Set<string>): string {
  return shared.has(player.short_name) ? `${player.name[0]}. ${player.short_name}` : player.short_name;
}

function Name({
  player,
  label,
  onSelectPlayer,
}: {
  player: Player;
  label: string;
  onSelectPlayer?: (player: Player) => void;
}) {
  if (!onSelectPlayer) return <span title={player.name}>{label}</span>;
  return (
    <button
      type="button"
      title={player.name}
      onClick={() => onSelectPlayer(player)}
      className="underline decoration-dotted underline-offset-2 hover:text-ku-blue dark:hover:text-ku-sky"
    >
      {label}
    </button>
  );
}

// The name column stays on screen while the rest scrolls; it needs the page's background behind it.
const stickyCell = "sticky left-0 z-[1] bg-slate-50 pl-4 dark:bg-slate-950";
