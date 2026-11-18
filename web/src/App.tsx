import { Navigate, Route, Routes } from "react-router";
import { useTeam } from "./api/queries";
import { Layout } from "./components/Layout";
import { Failed, Loading } from "./components/Status";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/games" replace />} />
        <Route path="games" element={<Placeholder />} />
        <Route path="*" element={<p className="text-slate-500">Page not found.</p>} />
      </Route>
    </Routes>
  );
}

/** Stands in for the Game log (next PR) and proves the typed API client works end to end. */
function Placeholder() {
  const team = useTeam();
  if (team.error) return <Failed error={team.error} />;
  if (!team.data) return <Loading what="the team" />;
  return <p className="text-slate-500">Tracking {team.data.name}. The Game log arrives in the next PR.</p>;
}
