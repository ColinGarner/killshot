import { useState } from "react";
import { Link, useParams } from "react-router";
import type { Player } from "../api/client";
import { useGame, useSeason, useTeam } from "../api/queries";
import { Killshots } from "../components/Killshots";
import { LineupTable } from "../components/LineupTable";
import { LiveBar, OnFloor } from "../components/LiveBar";
import { PlayerModal } from "../components/PlayerModal";
import { Failed, Loading, SectionTitle } from "../components/Status";
import { WinProbChart } from "../components/WinProbChart";
import { currentSeason, gameDate, venuePrefix } from "../lib/format";
import { advancedById } from "../lib/players";

/** One game: score, win probability over time, killshots, best and worst lineups. */
export function GamePage() {
  const { gameId = "" } = useParams();
  const team = useTeam();
  const game = useGame(team.data?.id, gameId);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  // The season a player's stats come from is the game's own season, not necessarily the
  // current one -- an old game should still show that season's numbers, not this year's.
  const season = game.data ? currentSeason(new Date(game.data.game.start_at)) : undefined;
  const seasonData = useSeason(season !== undefined ? team.data?.id : undefined, season ?? 0, false);
  const advanced = seasonData.data ? advancedById(seasonData.data.on_off) : {};

  if (team.error) return <Failed error={team.error} />;
  if (game.error) return <Failed error={game.error} />;
  if (!game.data) return <Loading what="the game" />;

  const { game: g, win_prob, killshots, lineups, min_poss, live } = game.data;
  return (
    <article className="space-y-8">
      {selectedPlayer && (
        <PlayerModal player={selectedPlayer} advanced={advanced[selectedPlayer.id]} onClose={() => setSelectedPlayer(null)} />
      )}
      <LiveBar detail={game.data} team={team.data?.name ?? ""} />
      <div>
        <Link to="/games" className="text-sm text-ku-blue hover:underline dark:text-ku-sky">
          ← Games
        </Link>
        <h2 className="mt-2 font-display text-2xl font-bold uppercase">
          <span className="text-slate-500">{venuePrefix(g.venue)}</span> {g.opponent.name}
        </h2>
        <p className="mt-1 flex items-baseline gap-3 tabular-nums">
          {!live && (
            <span className={`font-display text-3xl font-bold ${g.result === "W" ? "text-ku-blue dark:text-ku-sky" : "text-ku-crimson dark:text-ku-rose"}`}>
              {g.result} {g.pts}-{g.opp_pts}
            </span>
          )}
          <span className="text-sm text-slate-500">{gameDate(g.start_at)}</span>
        </p>
      </div>

      {live && live.on_floor.length > 0 && g.state !== "post" && (
        <section>
          <SectionTitle>On the floor</SectionTitle>
          <OnFloor detail={game.data} onSelectPlayer={setSelectedPlayer} />
        </section>
      )}

      <section>
        <SectionTitle>Win probability</SectionTitle>
        <WinProbChart points={win_prob} killshots={killshots} opponent={g.opponent.name} />
        <p className="mt-2 text-xs text-slate-500">
          {live
            ? "ESPN's win probability model, live. After the final it switches to CollegeBasketballData's, which can differ, especially early in the game."
            : "CollegeBasketballData's win probability model. During the game this showed ESPN's, which can differ, especially early."}
        </p>
      </section>

      <section>
        <SectionTitle>Killshots</SectionTitle>
        <Killshots killshots={killshots} opponent={g.opponent.name} />
      </section>

      <section>
        <SectionTitle>Most efficient lineups</SectionTitle>
        <LineupTable lineups={lineups.best} empty={`No lineup played ${min_poss}+ possessions.`} onSelectPlayer={setSelectedPlayer} />
      </section>

      <section>
        <SectionTitle>Least efficient lineups</SectionTitle>
        <LineupTable
          lineups={lineups.worst}
          empty={`Not enough lineups with ${min_poss}+ possessions.`}
          onSelectPlayer={setSelectedPlayer}
        />
        <p className="mt-3 text-xs text-slate-500">
          Lineups with {min_poss}+ possessions together. Net is points per 100 possessions scored minus allowed; +/− is the
          raw score margin while that five played. Small samples swing hard.
        </p>
      </section>
    </article>
  );
}
