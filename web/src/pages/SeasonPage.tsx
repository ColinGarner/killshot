import { useState } from "react";
import { useSearchParams } from "react-router";
import type { Ratings } from "../api/client";
import { useSeason, useTeam } from "../api/queries";
import { LineupTable, tone } from "../components/LineupTable";
import { OnOffTable } from "../components/OnOffTable";
import { Failed, Loading, SectionTitle } from "../components/Status";
import { currentSeason, signed } from "../lib/format";

const SEASONS = [currentSeason(), currentSeason() - 1];
const ON_OFF_MIN_MINUTES = 0.1; // share of the team's minutes a player needs for the on/off table

/** A season's lineups and on/off splits, with or without garbage time. */
export function SeasonPage() {
  const [params, setParams] = useSearchParams();
  // The controls keep their own state so they respond the instant they're touched; the URL
  // follows along (so the view can be shared) but updates as a background transition.
  const [season, setSeason] = useState(Number(params.get("season")) || SEASONS[0]);
  const [excludeGarbage, setExcludeGarbage] = useState(params.get("garbage") === "out");
  const team = useTeam();
  const data = useSeason(team.data?.id, season, excludeGarbage);
  const [chosenMinutes, setChosenMinutes] = useState<number | null>(null);

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  if (team.error) return <Failed error={team.error} />;
  if (data.error) return <Failed error={data.error} />;
  if (!data.data) return <Loading what="the season" />;

  const { totals, lineups, on_off } = data.data;
  // Early in a season few lineups have 40 minutes together, so start the slider lower.
  const minMinutes = chosenMinutes ?? ((totals?.minutes ?? 0) >= 600 ? 40 : 5);
  const shown = lineups.filter((l) => l.minutes >= minMinutes);
  const regulars = on_off.filter((r) => totals && r.on.minutes >= ON_OFF_MIN_MINUTES * totals.minutes);

  return (
    <article className="space-y-8">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <select
          id="season"
          aria-label="Season"
          value={season}
          onChange={(e) => {
            setChosenMinutes(null);
            setSeason(Number(e.target.value));
            setParam("season", e.target.value);
          }}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900"
        >
          {SEASONS.map((s) => (
            <option key={s} value={s}>
              {s - 1}-{String(s).slice(2)}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            id="garbage"
            type="checkbox"
            checked={excludeGarbage}
            onChange={(e) => {
              setExcludeGarbage(e.target.checked);
              setParam("garbage", e.target.checked ? "out" : null);
            }}
            className="size-4 accent-ku-blue"
          />
          Leave out garbage time
        </label>
      </div>
      <p className="-mt-5 text-xs text-slate-500">
        Garbage time: second half or overtime with the margin over 20. {data.isFetching && "Updating…"}
      </p>

      {totals && <TeamTiles totals={totals} />}

      <section>
        <SectionTitle>Lineups</SectionTitle>
        <label className="mb-3 flex items-center gap-3 text-sm text-slate-600 dark:text-slate-400">
          <span className="whitespace-nowrap">Together at least</span>
          <input
            id="min-minutes"
            type="range"
            min={0}
            max={150}
            step={1}
            value={minMinutes}
            onChange={(e) => setChosenMinutes(Number(e.target.value))}
            className="w-full max-w-56 accent-ku-blue"
          />
          <span className="shrink-0 font-semibold whitespace-nowrap text-ku-blue tabular-nums dark:text-ku-sky">{minMinutes} min</span>
        </label>
        <LineupTable lineups={shown} empty="No lineup has played that many minutes together. Lower the slider." />
        <p className="mt-3 text-xs text-slate-500">
          {shown.length} of {lineups.length} lineups, best net rating first. Small samples swing hard.
        </p>
      </section>

      <section>
        <SectionTitle>On/off</SectionTitle>
        <OnOffTable rows={regulars} />
        <p className="mt-3 text-xs text-slate-500">
          Team net rating with the player on the floor minus with him off: a measure of how the team does, not his own
          scoring. Players with at least {Math.round(ON_OFF_MIN_MINUTES * 100)}% of the team's minutes. Blowouts skew it;
          try leaving out garbage time.
        </p>
      </section>
    </article>
  );
}

function TeamTiles({ totals }: { totals: Ratings }) {
  const tiles: [string, string, string][] = [
    ["Net rating", signed(totals.net), tone(totals.net)],
    ["Offense", totals.ortg.toFixed(1), ""],
    ["Defense", totals.drtg.toFixed(1), ""],
    ["Possessions", totals.poss.toFixed(0), ""],
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map(([label, value, color]) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-ku-blue/5 p-3 dark:border-slate-800 dark:bg-ku-sky/5">
          <div className="font-display text-xs tracking-wider text-slate-500 uppercase">{label}</div>
          <div className={`font-display text-3xl font-bold tabular-nums ${color || "text-ku-blue dark:text-ku-sky"}`}>{value}</div>
        </div>
      ))}
    </div>
  );
}
