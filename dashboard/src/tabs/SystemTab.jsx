import { useState } from "react";
import { usePolling } from "../lib/usePolling.js";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import StatCard from "../components/StatCard.jsx";

const fmtUptime = (s) => {
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
};

export default function SystemTab() {
  const { data: info, error: infoErr, refresh } = usePolling(() => api.systemInfo(), 10000);
  const { data: ready } = usePolling(() => api.ready(), 10000);
  const { data: audit, refresh: refreshAudit } = usePolling(() => api.audit(30), 30000);
  const [msg, setMsg] = useState(null);
  const [days, setDays] = useState(90);
  const [metrics, setMetrics] = useState(null);

  async function act(fn, ok) {
    try {
      const r = await fn();
      setMsg({ ok: true, text: ok(r) });
      refresh(); refreshAudit();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  }

  const cache = info?.cache;
  return (
    <div>
      {infoErr && (
        <p className="mb-4 text-sm text-danger">
          Could not load system info: {infoErr.message}. This tab needs the admin key — set it in Settings.
        </p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Uptime" value={info ? fmtUptime(info.uptime_seconds) : null} />
        <StatCard label="Database" value={ready ? (ready.ok ? "Ready" : "Down") : null} accent={ready?.ok ? "text-emerald-600" : "text-danger"} />
        <StatCard label="URL model" value={info ? (info.url_model_loaded ? "Trained" : "Heuristic") : null} accent={info?.url_model_loaded ? "text-emerald-600" : "text-amber"} />
        <StatCard label="Live viewers" value={info?.live_subscribers} />
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <Panel title="Runtime">
          <dl className="p-4 text-sm grid grid-cols-2 gap-y-2">
            {info && [
              ["Version", info.version], ["Environment", info.environment], ["Python", info.python],
              ["Cache entries", cache ? `${cache.size} / ${cache.max_entries ?? "–"}` : "–"],
              ["Cache hit rate", cache?.hit_rate != null ? `${Math.round(cache.hit_rate * 100)}%` : "–"],
              ["Allow / deny rules", `${info.lists?.allow ?? 0} / ${info.lists?.deny ?? 0}`],
              ["Senders tracked", info.reputation_graph?.senders_tracked],
              ["Retention", info.retention_days ? `${info.retention_days} days` : "off"],
            ].map(([k, v]) => (
              <div key={k} className="contents"><dt className="text-slate">{k}</dt><dd className="text-ink">{String(v ?? "–")}</dd></div>
            ))}
          </dl>
        </Panel>

        <Panel title="Operations">
          <div className="p-4 space-y-4 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate">Reload the URL model from disk (clears cache)</span>
              <button className="bg-navy text-white rounded-lg px-3 py-1.5 text-xs font-semibold shadow-card hover:bg-navy-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal"
                onClick={() => act(api.reloadModels, (r) => r.note)}>Reload</button>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate">Delete verdicts older than</span>
              <span className="flex items-center gap-2">
                <input type="number" min="1" max="3650" value={days} onChange={(e) => setDays(Number(e.target.value))}
                  className="w-20 border border-line rounded-lg px-2.5 py-1.5 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal" /> days
                <button className="border border-red-200 text-danger rounded-lg px-3 py-1.5 text-xs font-semibold hover:bg-red-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
                  onClick={() => window.confirm(`Permanently delete verdicts older than ${days} days?`) &&
                    act(() => api.purge(days), (r) => `Deleted ${r.verdicts_deleted} verdicts, ${r.feedback_deleted} feedback rows.`)}>Purge</button>
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate">Prometheus metrics (raw)</span>
              <button className="border border-line rounded-lg px-3 py-1.5 text-xs font-semibold text-ink hover:bg-gray-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy"
                onClick={() => api.metricsText().then(setMetrics).catch((e) => setMsg({ ok: false, text: e.message }))}>View</button>
            </div>
            {msg && <p className={`text-xs ${msg.ok ? "text-emerald-600" : "text-danger"}`}>{msg.text}</p>}
          </div>
        </Panel>
      </div>

      {metrics && (
        <Panel title="/metrics" right={<button className="text-xs font-medium text-slate hover:text-ink" onClick={() => setMetrics(null)}>Close</button>}>
          <pre className="p-4 text-[11px] leading-snug overflow-auto max-h-80 text-slate font-mono-ui bg-gray-50">{metrics}</pre>
        </Panel>
      )}

      <Panel title="Audit log">
        {!audit?.length ? (
          <div className="p-6 text-center text-sm text-slate">No admin actions recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-slate text-[11px] font-semibold uppercase tracking-wide">
                {["Time", "Actor", "Action", "Detail", "IP"].map((h) => <th key={h} className="px-4 py-2 font-semibold">{h}</th>)}
              </tr></thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id} className="border-t border-line/70 hover:bg-gray-50/70 transition-colors">
                    <td className="px-4 py-2 whitespace-nowrap text-slate">{a.created_at ? new Date(a.created_at + "Z").toLocaleString() : ""}</td>
                    <td className="px-4 py-2 text-slate">{a.actor}</td>
                    <td className="px-4 py-2 text-ink">{a.action}</td>
                    <td className="px-4 py-2 max-w-xs truncate text-slate" title={a.detail}>{a.detail}</td>
                    <td className="px-4 py-2 text-slate">{a.ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
