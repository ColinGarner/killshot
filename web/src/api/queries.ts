// One hook per thing the pages show. TanStack Query caches each answer, so
// going back from a game to the list doesn't fetch the list again.
import { useQuery } from "@tanstack/react-query";
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
    queryFn: () =>
      unwrap(api.GET("/api/teams/{team_id}/games", { params: { path: { team_id: teamId! }, query: { season } } })),
  });
}

export function useGame(teamId: string | undefined, gameId: string) {
  return useQuery({
    queryKey: ["game", teamId, gameId],
    enabled: teamId !== undefined,
    queryFn: () =>
      unwrap(api.GET("/api/teams/{team_id}/games/{game_id}", { params: { path: { team_id: teamId!, game_id: gameId } } })),
  });
}
