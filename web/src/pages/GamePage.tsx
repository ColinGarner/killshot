import { Link, useParams } from "react-router";
import { useGame, useTeam } from "../api/queries";
import { Killshots } from "../components/Killshots";
import { LineupTable } from "../components/LineupTable";
import { Failed, Loading, SectionTitle } from "../components/Status";
import { WinProbChart } from "../components/WinProbChart";
import { gameDate, venuePrefix } from "../lib/format";

/** One game: score, win probability over time, killshots, best and worst lineups. */
export function GamePage() {
  const { gameId = "" } = useParams();
  const team = useTeam();
  const game = useGame(team.data?.id, gameId);

  if (team.error) return <Failed error={team.error} />;
  if (game.error) return <Failed error={game.error} />;
  if (!game.data) return <Loading what="the game" />;

  const { game: g, win_prob, killshots, lineups, min_poss } = game.data;
  return (
    <article className="space-y-8">
      <div>
        <Link to="/games" className="text-sm text-ku-blue hover:underline dark:text-ku-sky">
          ← Games
        </Link>
        <h2 className="mt-2 font-display text-2xl font-bold uppercase">
          <span className="text-slate-500">{venuePrefix(g.venue)}</span> {g.opponent.name}
        </h2>
        <p className="mt-1 flex items-baseline gap-3 tabular-nums">
          <span className={`font-display text-3xl font-bold ${g.result === "W" ? "text-ku-blue dark:text-ku-sky" : "text-ku-crimson dark:text-ku-rose"}`}>
            {g.result} {g.pts}-{g.opp_pts}
          </span>
          <span className="text-sm text-slate-500">{gameDate(g.start_at)}</span>
        </p>
      </div>

      <section>
        <SectionTitle>Win probability</SectionTitle>
        <WinProbChart points={win_prob} killshots={killshots} opponent={g.opponent.name} />
      </section>

      <section>
        <SectionTitle>Killshots</SectionTitle>
        <Killshots killshots={killshots} opponent={g.opponent.name} />
      </section>

      <section>
        <SectionTitle>Most efficient lineups</SectionTitle>
        <LineupTable lineups={lineups.best} empty={`No lineup played ${min_poss}+ possessions.`} />
      </section>

      <section>
        <SectionTitle>Least efficient lineups</SectionTitle>
        <LineupTable lineups={lineups.worst} empty={`Not enough lineups with ${min_poss}+ possessions.`} />
        <p className="mt-3 text-xs text-slate-500">
          Lineups with {min_poss}+ possessions together. Net is points per 100 possessions scored minus allowed; +/− is the
          raw score margin while that five played. Small samples swing hard.
        </p>
      </section>
    </article>
  );
}
