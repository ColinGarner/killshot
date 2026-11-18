import { NavLink, Outlet } from "react-router";

/** The KU-blue band with the crimson stripe, the tabs, and the page below. */
export function Layout() {
  return (
    <div className="min-h-dvh pb-[env(safe-area-inset-bottom)]">
      <header className="bg-ku-blue pt-[env(safe-area-inset-top)] text-white shadow-[inset_0_-6px_0_var(--color-ku-crimson),inset_0_-8px_0_white]">
        <div className="mx-auto max-w-3xl px-4 pt-5 pb-7">
          <p className="font-display text-xs tracking-[0.14em] uppercase opacity-85">Kansas Jayhawks · Men's Basketball</p>
          <h1 className="font-display text-4xl font-bold tracking-wide uppercase">
            Kill<span className="underline decoration-ku-crimson decoration-[0.12em] underline-offset-[0.12em]">shot</span>
          </h1>
        </div>
      </header>
      <nav className="mx-auto flex max-w-3xl gap-1 border-b-2 border-slate-200 px-4 dark:border-slate-800" aria-label="Sections">
        <Tab to="/games">Game log</Tab>
      </nav>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function Tab({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `-mb-0.5 border-b-[3px] px-3 py-2.5 font-display text-sm font-bold tracking-widest uppercase ${
          isActive ? "border-ku-crimson text-ku-blue dark:text-ku-sky" : "border-transparent text-slate-500"
        }`
      }
    >
      {children}
    </NavLink>
  );
}
