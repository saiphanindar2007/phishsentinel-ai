import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import { RefreshCw, Download, ChevronLeft, ChevronRight } from "lucide-react";

const FILTERS = ["all", "safe", "suspicious", "phishing"];
const PAGE = 25;

export default function HistoryTab() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(query.trim()); setPage(0); }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.verdictsPage({ limit: PAGE, offset: page * PAGE, verdict: filter, q: debounced });
      setRows(r.rows);
      setTotal(r.total);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, filter, debounced]);

  useEffect(() => { load(); }, [load]);

  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <Panel
      title={`Verdict History (${total})`}
      right={
        <div className="flex items-center gap-4">
          <button onClick={() => api.exportCsv({ verdict: filter, q: debounced }).catch((e) => setError(e.message))}
            className="flex items-center gap-1.5 text-xs text-slate hover:text-ink">
            <Download size={13} /> Export CSV
          </button>
          <button onClick={load} className="flex items-center gap-1.5 text-xs text-slate hover:text-ink">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>
      }
    >
      <div className="px-4 py-3 flex flex-wrap gap-2 border-b border-line">
        <input
          className="flex-1 min-w-[200px] border border-line rounded-lg px-3 py-2 text-sm placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
          placeholder="Search by URL / sender…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => { setFilter(f); setPage(0); }}
              className={`px-3 py-1.5 rounded-lg text-xs capitalize ${filter === f ? "bg-navy text-white shadow-card" : "bg-gray-100 text-slate hover:bg-gray-200/80"}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="px-4 py-2 text-xs text-danger">Error: {error}</p>}

      {!rows.length ? (
        <div className="p-8 text-center text-sm text-slate">{loading ? "Loading…" : "No verdicts match."}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate text-[11px] font-semibold uppercase tracking-wide">
                {["Verdict", "Confidence", "Type", "Input", "Time"].map((h) => <th key={h} className="px-4 py-2 font-semibold">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => (
                <tr key={v.verdict_id} className="border-t border-line/70 hover:bg-gray-50/70 transition-colors" title={v.explanation}>
                  <td className="px-4 py-2"><Badge verdict={v.verdict} /></td>
                  <td className="px-4 py-2">{Math.round(v.confidence * 100)}%</td>
                  <td className="px-4 py-2 capitalize text-slate">{v.input_type}</td>
                  <td className="px-4 py-2 max-w-xs truncate text-slate">{v.raw_input}</td>
                  <td className="px-4 py-2 text-slate whitespace-nowrap">{v.created_at ? new Date(v.created_at + "Z").toLocaleString() : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="px-4 py-3 flex items-center justify-between text-xs text-slate border-t border-line">
        <span>Page {page + 1} of {pages}</span>
        <div className="flex gap-1">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronLeft size={14} /></button>
          <button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronRight size={14} /></button>
        </div>
      </div>
    </Panel>
  );
}
