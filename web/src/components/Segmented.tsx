/** A row of buttons where exactly one is chosen, like iOS's segmented control. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string; // for screen readers: what this choice is about
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-lg bg-slate-200/70 p-0.5 dark:bg-slate-800"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-3 py-1.5 font-display text-sm font-bold tracking-wide uppercase ${
            o.value === value ? "bg-white text-ku-blue shadow-sm dark:bg-slate-950 dark:text-ku-sky" : "text-slate-500"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
