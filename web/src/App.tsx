import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { Loading } from "./components/Status";
import { GamesPage } from "./pages/GamesPage";

// The game page carries the chart library (Recharts, the biggest dependency), so it's
// downloaded only when someone opens a game. The game list loads without it.
const GamePage = lazy(() => import("./pages/GamePage").then((m) => ({ default: m.GamePage })));

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/games" replace />} />
        <Route path="games" element={<GamesPage />} />
        <Route
          path="games/:gameId"
          element={
            <Suspense fallback={<Loading what="the game" />}>
              <GamePage />
            </Suspense>
          }
        />
        <Route path="*" element={<p className="text-slate-500">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
