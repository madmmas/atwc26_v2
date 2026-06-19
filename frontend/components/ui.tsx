// Small shared presentational helpers.
export function RoleChip({ role }: { role: string }) {
  return <span className={`chip role-${role}`}>{role}</span>;
}

export function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wider text-faint">{label}</div>
      <div className="mt-1 text-3xl font-black stat-grad">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-faint">{sub}</div>}
    </div>
  );
}

export function SectionTitle({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-3 flex items-end justify-between">
      <h2 className="text-lg font-bold text-fg">{title}</h2>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-pitch-edge border-t-pitch-accent" />
      {label || "Loading…"}
    </div>
  );
}
