/** What a section shows while its data loads, or if loading failed. */
export function Loading({ what }: { what: string }) {
  return <p className="py-8 text-center text-sm text-slate-500">Loading {what}…</p>;
}

export function Failed({ error }: { error: Error }) {
  return (
    <p className="rounded-lg border border-ku-crimson/40 bg-ku-crimson/5 p-4 text-sm text-ku-crimson dark:text-ku-rose">
      Couldn't load this: {error.message}
    </p>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 font-display text-lg font-bold tracking-wide text-ku-blue uppercase dark:text-ku-sky">{children}</h2>;
}
