export default function StatCard({ label, value, accent = "text-ink", icon: Icon, hint }) {
  return (
    <div className="bg-white rounded-2xl border border-line shadow-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] uppercase tracking-wide text-slate font-semibold">{label}</div>
        {Icon && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gray-50 text-slate">
            <Icon size={13} />
          </span>
        )}
      </div>
      <div className={`text-2xl font-bold mt-1.5 tabular-nums ${accent}`}>{value ?? "–"}</div>
      {hint && <div className="text-[11px] text-slate mt-1">{hint}</div>}
    </div>
  );
}
