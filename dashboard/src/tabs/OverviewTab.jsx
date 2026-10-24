import { usePolling } from "../lib/usePolling.js";
import { api } from "../lib/api.js";
import StatCard from "../components/StatCard.jsx";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const hourLabel = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function OverviewTab() {
  const { data: stats } = usePolling(() => api.stats(), 15000);
  const { data: ready } = usePolling(() => api.ready(), 10000);
  const { data: verdicts } = usePolling(() => api.verdicts(6), 15000);
  const { data: timeline } = usePolling(() => api.timeline(24), 60000);
  const { data: domains } = usePolling(() => api.topDomains(6), 60000);

  const flaggedRate = stats?.total ? Math.round(((stats.phishing + stats.suspicious) / stats.total) * 100) : null;

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <StatCard label="Total Analyzed" value={stats?.total} />
        <StatCard label="Flagged Phishing" value={stats?.phishing} accent="text-danger" />
        <StatCard label="Suspicious" value={stats?.suspicious} accent="text-amber" />
        <StatCard label="Safe" value={stats?.safe} accent="text-emerald-600" />
        <StatCard label="Flag Rate" value={flaggedRate == null ? null : `${flaggedRate}%`} />
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        <Panel title="Last 24 hours" className="md:col-span-2">
          <div className="p-4 h-56">
            {!timeline ? null : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E6EAF0" />
                  <XAxis dataKey="hour" tickFormatter={hourLabel} tick={{ fontSize: 11 }} minTickGap={24} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                  <Tooltip labelFormatter={hourLabel} />
                  <Area type="monotone" dataKey="safe" stackId="1" stroke="#10B981" fill="#10B98126" />
                  <Area type="monotone" dataKey="suspicious" stackId="1" stroke="#D97706" fill="#D9770626" />
                  <Area type="monotone" dataKey="phishing" stackId="1" stroke="#DC2626" fill="#DC262626" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel title="Top flagged domains (7d)">
          {!domains?.length ? (
            <div className="p-6 text-center text-sm text-slate">Nothing flagged yet.</div>
          ) : (
            <ul className="divide-y divide-line">
              {domains.map((d) => (
                <li key={d.domain} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <span className="truncate text-ink">{d.domain}</span>
                  <span className="flex items-center gap-2 shrink-0 ml-2">
                    <Badge verdict={d.worst_verdict} />
                    <span className="text-xs text-slate w-6 text-right">{d.count}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        <Panel title="System" className="md:col-span-1">
          <div className="p-4 space-y-3 text-sm">
            <Row label="Backend API" ok={!!ready} okText="Online" badText="Unreachable" />
            <Row label="Database" ok={ready?.ok} okText="Ready" badText="Down" />
          </div>
        </Panel>

        <Panel title="Most Recent Verdicts" className="md:col-span-2">
          {!verdicts?.length ? (
            <div className="p-6 text-center text-sm text-slate">No verdicts yet — run a check in the Analyzer tab.</div>
          ) : (
            <ul className="divide-y divide-line">
              {verdicts.map((v) => (
                <li key={v.verdict_id} className="px-4 py-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-3 min-w-0">
                    <Badge verdict={v.verdict} />
                    <span className="truncate text-slate">{v.raw_input}</span>
                  </div>
                  <span className="text-xs text-slate shrink-0 ml-3">{Math.round(v.confidence * 100)}%</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Row({ label, ok, okText, badText }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate">{label}</span>
      <span className={`font-medium ${ok ? "text-emerald-600" : "text-danger"}`}>{ok ? okText : badText}</span>
    </div>
  );
}
