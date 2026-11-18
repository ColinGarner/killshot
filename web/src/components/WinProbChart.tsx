import { Area, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Killshot, WinProbPoint } from "../api/client";

const BLUE = "var(--color-ku-blue)";
const CRIMSON = "var(--color-ku-crimson)";

/** Game seconds elapsed -> axis label. Regulation is 0-2400; each overtime adds 300. */
function tickLabel(t: number): string {
  return ({ 0: "Tip", 600: "10:00", 1200: "Half", 1800: "10:00", 2400: "End" } as Record<number, string>)[t] ?? `OT${(t - 2400) / 300}`;
}

/**
 * This team's win probability over the game. Above 50% is shaded KU blue,
 * below is crimson; killshots are shaded bands with their score ("12-0").
 */
export function WinProbChart({ points, killshots, opponent }: { points: WinProbPoint[]; killshots: Killshot[]; opponent: string }) {
  if (points.length === 0) {
    return <p className="py-6 text-sm text-slate-500">No win probability for this game: CollegeBasketballData doesn't have it.</p>;
  }
  // Each point's distance above or below 50%, for the two shaded areas.
  const data = points.map((p) => ({ ...p, above: Math.max(p.win_prob, 50), below: Math.min(p.win_prob, 50) }));
  const last = points[points.length - 1].t;
  const end = last <= 2400 ? 2400 : 2400 + Math.ceil((last - 2400) / 300) * 300;
  const ticks = [0, 600, 1200, 1800, 2400];
  for (let t = 2700; t <= end; t += 300) ticks.push(t);

  return (
    <div className="h-64 w-full sm:h-72" role="img" aria-label={`Win probability, ending at ${Math.round(points[points.length - 1].win_prob)}%`}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 18, right: 8, bottom: 0, left: -18 }}>
          {killshots.map((k) => (
            <ReferenceArea
              key={`${k.t0}-${k.t1}`}
              x1={k.t0}
              x2={Math.max(k.t1, k.t0 + 5)}
              fill={k.by === "team" ? BLUE : CRIMSON}
              fillOpacity={0.12}
              label={{ value: k.label, position: "top", fill: k.by === "team" ? BLUE : CRIMSON, fontSize: 11, fontWeight: 700 }}
            />
          ))}
          <XAxis dataKey="t" type="number" domain={[0, end]} ticks={ticks} tickFormatter={tickLabel} tick={{ fontSize: 11 }} stroke="currentColor" className="text-slate-400" />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11 }} stroke="currentColor" className="text-slate-400" />
          <ReferenceLine y={50} stroke="currentColor" strokeDasharray="4 4" className="text-slate-400" />
          <ReferenceLine x={1200} stroke="currentColor" className="text-slate-300 dark:text-slate-700" />
          {/* Two shaded areas measured from the 50% line: KU's side above it in blue, the opponent's below it in crimson. */}
          <Area type="linear" dataKey="above" baseValue={50} stroke="none" fill={BLUE} fillOpacity={0.22} isAnimationActive={false} />
          <Area type="linear" dataKey="below" baseValue={50} stroke="none" fill={CRIMSON} fillOpacity={0.22} isAnimationActive={false} />
          <Line type="linear" dataKey="win_prob" stroke={BLUE} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Tooltip content={<PointTooltip opponent={opponent} />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function PointTooltip({ active, payload, opponent }: { active?: boolean; payload?: { payload: WinProbPoint }[]; opponent: string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-slate-700 dark:bg-slate-900">
      <div className="font-semibold">{p.clock}</div>
      <div>KU win probability {p.win_prob.toFixed(1)}%</div>
      <div className="text-slate-500">KU {p.pts}, {opponent} {p.opp_pts}</div>
    </div>
  );
}
