import { useState } from "react";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import StatCard from "../components/StatCard.jsx";
import { usePolling } from "../lib/usePolling.js";
import { Loader2, CheckCircle2, XCircle, PlayCircle } from "lucide-react";

export default function ReviewTab() {
  const [statusFilter, setStatusFilter] = useState("pending");
  const { data: summary, refresh: refreshSummary } = usePolling(() => api.reviewQueueSummary(), 15000);
  const { data: queue, refresh: refreshQueue } = usePolling(
    () => api.reviewQueue(statusFilter === "all" ? undefined : statusFilter),
    15000,
    [statusFilter]
  );

  async function refreshAll() {
    await Promise.all([refreshSummary(), refreshQueue()]);
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Pending Review" value={summary?.pending} accent="text-amber" />
        <StatCard label="Upheld" value={summary?.upheld} accent="text-emerald-600" />
        <StatCard label="Overturned" value={summary?.overturned} accent="text-danger" />
        <StatCard label="Total Flagged" value={summary?.total} />
      </div>

      <Panel
        title="Analyst Review Queue"
        right={
          <div className="flex gap-1 text-xs">
            {["pending", "upheld", "overturned", "all"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                  statusFilter === s ? "bg-navy text-white shadow-card" : "text-slate hover:bg-gray-100"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        }
      >
        {!queue?.items?.length ? (
          <div className="p-8 text-center text-sm text-slate">
            No {statusFilter === "all" ? "" : statusFilter} items in the review queue. Flag a verdict from the
            Analyzer tab to send it here.
          </div>
        ) : (
          <div className="divide-y divide-line">
            {queue.items.map((item) => (
              <ReviewRow key={item.id} item={item} onResolved={refreshAll} />
            ))}
          </div>
        )}
      </Panel>

      <EvalBenchPanel />
    </div>
  );
}

function ReviewRow({ item, onResolved }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [label, setLabel] = useState("phishing");
  const v = item.verdict;

  async function resolve(outcome) {
    setBusy(true);
    try {
      await api.resolveReview(item.id, {
        outcome,
        actual_label: outcome === "overturned" ? label : undefined,
        note: note || undefined,
      });
      onResolved?.();
    } catch {
      /* best-effort UI refresh; the queue poll will catch up regardless */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-4 space-y-2 hover:bg-gray-50/50 transition-colors">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Badge verdict={v?.verdict || "safe"} />
          <span className="text-xs font-mono-ui text-slate truncate max-w-[22rem]">{v?.raw_input}</span>
        </div>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full uppercase ${
          item.status === "pending" ? "bg-amber-100 text-amber-700"
          : item.status === "upheld" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-danger"
        }`}>
          {item.status}
        </span>
      </div>
      {item.flagged_note && <p className="text-xs text-slate">Analyst note: {item.flagged_note}</p>}
      {v?.explanation && <p className="text-xs text-slate">{v.explanation}</p>}

      {item.status === "pending" ? (
        <div className="flex items-center gap-2 flex-wrap pt-1">
          <select
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="text-xs border border-line rounded-lg px-2.5 py-1.5 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
          >
            <option value="safe">safe</option>
            <option value="suspicious">suspicious</option>
            <option value="phishing">phishing</option>
          </select>
          <input
            className="text-xs border border-line rounded-lg px-2.5 py-1.5 flex-1 min-w-[10rem] transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
            placeholder="Resolution note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            onClick={() => resolve("upheld")}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-600 text-white shadow-card hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />} Uphold
          </button>
          <button
            onClick={() => resolve("overturned")}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-danger text-white shadow-card hover:bg-red-700 transition-colors disabled:opacity-50"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />} Overturn to "{label}"
          </button>
        </div>
      ) : (
        <p className="text-xs text-slate">
          Resolved as <b>{item.status}</b>{item.actual_label ? ` → ${item.actual_label}` : ""}
          {item.resolved_note ? ` — ${item.resolved_note}` : ""}
        </p>
      )}
    </div>
  );
}

function EvalBenchPanel() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const { data: runs, refresh: refreshRuns } = usePolling(() => api.evalRuns(10), 30000);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await api.runEvaluation();
      setResult(r);
      await refreshRuns();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Panel
      title="Reproducible Evaluation Bench"
      right={
        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-lg bg-navy text-white shadow-card hover:bg-navy-4 transition-colors disabled:opacity-60"
        >
          {running ? <Loader2 size={13} className="animate-spin" /> : <PlayCircle size={13} />}
          Run evaluation
        </button>
      }
    >
      <div className="p-4 space-y-3">
        <p className="text-xs text-slate">
          Scores the fixed, version-controlled labelled URL set (<code>backend/eval/labeled_urls.csv</code>) through
          the live detector and fusion code — same model, same thresholds, same dataset hash every run, so results
          are directly comparable across commits.
        </p>
        {error && <p className="text-xs text-danger">Error: {error}</p>}
        {result && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Accuracy" value={`${Math.round(result.accuracy * 100)}%`} />
            <StatCard label="Macro F1" value={result.macro_f1} />
            <StatCard label="Dataset" value={result.dataset_size} />
            <StatCard label="Hash" value={result.dataset_sha256_16} />
          </div>
        )}
        {result?.mismatches?.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer select-none text-slate font-medium">
              {result.mismatches.length} mismatch(es) in this run
            </summary>
            <ul className="mt-2 space-y-1 font-mono-ui">
              {result.mismatches.map((m) => (
                <li key={m.url} className="text-slate">
                  {m.url} — labelled <b>{m.label}</b>, predicted <b>{m.predicted}</b> ({m.confidence})
                </li>
              ))}
            </ul>
          </details>
        )}
        {runs?.length > 0 && (
          <div>
            <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2 mt-2">Run history</div>
            <table className="w-full text-xs">
              <thead className="text-slate text-left text-[11px] font-semibold uppercase tracking-wide">
                <tr><th className="font-semibold pb-2">Run</th><th className="font-semibold pb-2">Accuracy</th><th className="font-semibold pb-2">Macro F1</th><th className="font-semibold pb-2">Dataset hash</th></tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-t border-line hover:bg-gray-50/70 transition-colors">
                    <td className="py-1 font-mono-ui">{r.run_id}</td>
                    <td className="py-1">{r.accuracy != null ? `${Math.round(r.accuracy * 100)}%` : "–"}</td>
                    <td className="py-1">{r.macro_f1 ?? "–"}</td>
                    <td className="py-1 font-mono-ui">{r.dataset_sha256_16}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}
