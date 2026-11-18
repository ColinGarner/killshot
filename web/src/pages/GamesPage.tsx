import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import type { GameSummary } from "../api/client";
import { useGames, useTeam } from "../api/queries";
import { Failed, Loading } from "../components/Status";
import { currentSeason, gameDate, tipTime, venuePrefix } from "../lib/format";

const SEASONS = [currentSeason(), currentSeason() - 1];

/** The season's schedule and results. Tap a played game for its lineups and chart. */
export function GamesPage() {
  const [params, setParams] = useSearchParams();
  // Own state so the picker changes instantly; the URL follows in the background.
  const [season, setSeason] = useState(Number(params.get("season")) || SEASONS[0]);
  const team = useTeam();
  const games = useGames(team.data?.id, season);

  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-display text-lg font-bold tracking-wide text-ku-blue uppercase dark:text-ku-sky">Games</h2>
        <label className="flex items-center gap-2 text-sm text-slate-500">
          <span className="sr-only">Season</span>
          <select
            id="season"
            value={season}
            onChange={(e) => {
              setSeason(Number(e.target.value));
              setParams({ season: e.target.value }, { replace: true });
            }}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {SEASONS.map((s) => (
              <option key={s} value={s}>
                {s - 1}-{String(s).slice(2)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {team.error && <Failed error={team.error} />}
      {games.error && <Failed error={games.error} />}
      {games.isPending && !games.error && <Loading what="games" />}
      {games.data && (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {games.data.map((g) => (
            <li key={g.id}>
              <GameRow game={g} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function GameRow({ game: g }: { game: GameSummary }) {
  const body = (
    <div className="flex items-center gap-3 py-3">
      <span className="w-14 shrink-0 text-sm text-slate-500 tabular-nums">{gameDate(g.start_at)}</span>
      <span className="min-w-0 flex-1 truncate">
        <span className="text-slate-500">{venuePrefix(g.venue)} </span>
        <span className="font-semibold">{g.opponent.name}</span>
      </span>
      <Result game={g} />
    </div>
  );
  // Games with play-by-play have a page worth opening, and so does a game that's on.
  return g.has_plays || g.live ? (
    <Link to={`/games/${g.id}`} className="block rounded-md hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-ku-blue dark:hover:bg-slate-900">
      {body}
    </Link>
  ) : (
    body
  );
}

function Result({ game: g }: { game: GameSummary }) {
  if (g.state === "pre") return <span className="text-sm text-slate-500">{g.time_tbd ? "Time TBA" : tipTime(g.start_at)}</span>;
  if (g.state === "in")
    return (
      <span className="flex items-baseline gap-2 tabular-nums">
        <span className="font-display text-sm font-bold tracking-wider text-ku-crimson uppercase dark:text-ku-rose">● Live</span>
        {g.live && (
          <span className="font-semibold">
            {g.pts}-{g.opp_pts}
          </span>
        )}
      </span>
    );
  return (
    <span className="flex items-baseline gap-2 tabular-nums">
      <span className={`font-display font-bold ${g.result === "W" ? "text-ku-blue dark:text-ku-sky" : "text-ku-crimson dark:text-ku-rose"}`}>
        {g.result}
      </span>
      <span className="font-semibold">
        {g.pts}-{g.opp_pts}
      </span>
      {!g.has_plays && !g.live && <span className="text-xs text-slate-500">stats soon</span>}
    </span>
  );
}
