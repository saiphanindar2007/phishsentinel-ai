import { useState } from "react";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import { Loader2, Download, Upload } from "lucide-react";

const MAX = 100;
const cell = (v) => {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // neutralise spreadsheet formulas
  return `"${s.replace(/"/g, '""')}"`;
};

function parseUrls(text) {
  const seen = new Set();
  return text
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter((s) => s && !seen.has(s) && seen.add(s));
}

export default function BatchTab() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const urls = parseUrls(text);

  async function run() {
    setError(null);
    setResult(null);
    if (!urls.length) return;
    if (urls.length > MAX) {
      setError(`Too many URLs (${urls.length}). Maximum is ${MAX} per scan.`);
      return;
    }
    setLoading(true);
    try {
      setResult(await api.analyzeBatch(urls));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 1_000_000) return setError("File too large (max 1 MB).");
    const r = new FileReader();
    r.onload = () => setText(String(r.result));
    r.readAsText(f);
    e.target.value = "";
  }

  function download() {
    const lines = [["url", "verdict", "confidence", "reasons"].map(cell).join(",")];
    result.results.forEach((r) => lines.push([r.input, r.verdict, r.confidence, r.top_reasons.join("; ")].map(cell).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = "phishsentinel-batch.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  return (
    <div className="grid lg:grid-cols-5 gap-5">
      <Panel title="Batch Scan" className="lg:col-span-2">
        <div className="p-4 space-y-3">
          <textarea
            className="w-full border border-line rounded-lg px-3 py-2 text-sm h-56 font-mono-ui placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
            placeholder={"Paste URLs — one per line, or separated by spaces/commas.\nhttps://example.com\nhttp://paypa1-login.tk/verify"}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center justify-between text-xs text-slate">
            <span className={urls.length > MAX ? "text-danger" : ""}>{urls.length} unique URL(s) · max {MAX}</span>
            <label className="flex items-center gap-1 cursor-pointer hover:text-ink">
              <Upload size={13} /> Load .txt/.csv
              <input type="file" accept=".txt,.csv,text/plain" className="hidden" onChange={onFile} />
            </label>
          </div>
          <button
            onClick={run}
            disabled={loading || !urls.length}
            className="w-full bg-navy text-white rounded-lg py-2.5 text-sm font-semibold flex items-center justify-center gap-2 shadow-card hover:bg-navy-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal"
          >
            {loading && <Loader2 size={14} className="animate-spin" />} Scan {urls.length || ""} URL{urls.length === 1 ? "" : "s"}
          </button>
          {error && <p className="text-xs text-danger">Error: {error}</p>}
        </div>
      </Panel>

      <Panel
        title="Results"
        className="lg:col-span-3"
        right={result && (
          <button onClick={download} className="flex items-center gap-1.5 text-xs text-slate hover:text-ink">
            <Download size={13} /> CSV
          </button>
        )}
      >
        {!result ? (
          <div className="p-8 text-center text-sm text-slate">Results appear here, worst first.</div>
        ) : (
          <>
            <div className="px-4 py-3 flex gap-4 text-sm border-b border-line">
              <span className="text-danger font-semibold">{result.summary.phishing} phishing</span>
              <span className="text-amber font-semibold">{result.summary.suspicious} suspicious</span>
              <span className="text-emerald-600 font-semibold">{result.summary.safe} safe</span>
            </div>
            <ul className="divide-y divide-line max-h-[480px] overflow-y-auto">
              {[...result.results].sort((a, b) => b.confidence - a.confidence).map((r) => (
                <li key={r.verdict_id} className="px-4 py-2.5 text-sm flex items-start gap-3">
                  <Badge verdict={r.verdict} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-ink">{r.input}</div>
                    <div className="text-xs text-slate truncate">{r.top_reasons[0]}</div>
                  </div>
                  <span className="text-xs text-slate">{Math.round(r.confidence * 100)}%</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Panel>
    </div>
  );
}
