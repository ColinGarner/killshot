// One hook per thing the pages show. TanStack Query caches each answer, so
// going back from a game to the list doesn't fetch the list again.
import { useQuery } from "@tanstack/react-query";
import { LIVE_REFRESH_MS, isGameTime } from "../lib/live";
import { api, unwrap } from "./client";

export function useTeams() {
  return useQuery({ queryKey: ["teams"], queryFn: () => unwrap(api.GET("/api/teams")), staleTime: Infinity });
}

/** The team this site shows. Today that's Kansas, the only tracked team. */
export function useTeam() {
  const teams = useTeams();
  return { ...teams, data: teams.data?.[0] };
}

export function useGames(teamId: string | undefined, season: number) {
  return useQuery({
    queryKey: ["games", teamId, season],
    enabled: teamId !== undefined,
    // While a game is on, or about to be, keep the list's live scores fresh.
    refetchInterval: (query) =>
      query.state.data?.some((g) => g.state === "in" || g.live || isGameTime(g.start_at)) ? LIVE_REFRESH_MS : false,
    queryFn: () =>
      unwrap(api.GET("/api/teams/{team_id}/games", { params: { path: { team_id: teamId! }, query: { season } } })),
  });
}

export function useGame(teamId: string | undefined, gameId: string) {
  return useQuery({
    queryKey: ["game", teamId, gameId],
    enabled: teamId !== undefined,
    // A live game asks for new data every 30 seconds (the worker reads ESPN that often),
    // and so does a game around its tip time that isn't live yet, so it goes live by itself.
    // Once CBBD's official record replaces it, the refreshing stops.
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && (d.live || (!d.game.has_plays && isGameTime(d.game.start_at))) ? LIVE_REFRESH_MS : false;
    },
    queryFn: () =>
      unwrap(api.GET("/api/teams/{team_id}/games/{game_id}", { params: { path: { team_id: teamId!, game_id: gameId } } })),
  });
}

/**
 * A season's totals, every lineup and every player's on/off split. The page filters
 * lineups by minutes itself, so moving the slider doesn't wait on the network.
 */
export function useSeason(teamId: string | undefined, season: number, excludeGarbage: boolean) {
  return useQuery({
    queryKey: ["season", teamId, season, excludeGarbage],
    enabled: teamId !== undefined,
    placeholderData: (previous) => previous, // keep showing the last numbers while the toggle refetches
    queryFn: () =>
      unwrap(
        api.GET("/api/teams/{team_id}/seasons/{season}", {
          params: { path: { team_id: teamId!, season }, query: { min_minutes: 0, exclude_garbage: excludeGarbage } },
        }),
      ),
  });
}
