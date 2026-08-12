export function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string | undefined; // exactOptionalPropertyTypes: callers pass explicit undefined
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-100">{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}
