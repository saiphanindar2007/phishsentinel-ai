import { useState } from "react";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import { ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";

const SIGNAL_LABELS = {
  url_score: "URL & Domain Intelligence",
  nlp_score: "NLP Content Classifier",
  visual_score: "Visual Impersonation Check",
  reputation_score: "Sender Reputation Graph",
};

export default function AnalyzerTab() {
  const [mode, setMode] = useState("url");
  const [url, setUrl] = useState("");
  const [email, setEmail] = useState({ sender: "", subject: "", body: "", url: "", html_body: "", raw_headers: "" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [flagSent, setFlagSent] = useState(false);

  async function runUrlCheck() {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setFeedbackSent(false);
    setFlagSent(false);
    try {
      setResult(await api.analyzeUrl(url.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function runEmailCheck() {
    if (!email.sender.trim() || !email.body.trim()) return;
    setLoading(true);
    setError(null);
    setFeedbackSent(false);
    setFlagSent(false);
    try {
      const payload = Object.fromEntries(Object.entries(email).filter(([, v]) => String(v).trim() !== ""));
      setResult(await api.analyzeEmail(payload));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function flagForReview() {
    if (!result) return;
    try {
      await api.flagForReview({ verdict_id: result.verdict_id, source: "web" });
      setFlagSent(true);
    } catch {
      /* silent — flagging is best-effort from the UI's perspective */
    }
  }

  async function sendFeedback(isCorrect) {
    if (!result) return;
    try {
      await api.sendFeedback({
        verdict_id: result.verdict_id,
        is_correct: isCorrect,
        actual_label: isCorrect ? undefined : result.verdict === "safe" ? "phishing" : "safe",
        source: "web",
      });
      setFeedbackSent(true);
    } catch {
      /* silent — feedback is best-effort from the UI's perspective */
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      <Panel
        title="Run a Check"
        right={
          <div className="flex gap-1 text-xs">
            {["url", "email"].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                  mode === m ? "bg-navy text-white shadow-card" : "text-slate hover:bg-gray-100"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        }
      >
        <div className="p-4 space-y-3">
          {mode === "url" ? (
            <>
              <input
                className="w-full border border-line rounded-lg px-3 py-2 text-sm placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                placeholder="https://paypa1-secure-login.com/verify"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runUrlCheck()}
              />
              <button
                onClick={runUrlCheck}
                disabled={loading}
                className="w-full bg-navy text-white rounded-lg py-2.5 text-sm font-semibold flex items-center justify-center gap-2 shadow-card hover:bg-navy-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                Analyze URL
              </button>
            </>
          ) : (
            <>
              <input
                className="w-full border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                placeholder="Sender address, e.g. security@paypa1-alerts.tk"
                value={email.sender}
                onChange={(e) => setEmail({ ...email, sender: e.target.value })}
              />
              <input
                className="w-full border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                placeholder="Subject"
                value={email.subject}
                onChange={(e) => setEmail({ ...email, subject: e.target.value })}
              />
              <input
                className="w-full border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                placeholder="Link in the email (optional)"
                value={email.url}
                onChange={(e) => setEmail({ ...email, url: e.target.value })}
              />
              <textarea
                className="w-full border border-line rounded-lg px-3 py-2 text-sm h-24 resize-none placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                placeholder="Paste the email body text…"
                value={email.body}
                onChange={(e) => setEmail({ ...email, body: e.target.value })}
              />
              <details className="text-xs text-slate">
                <summary className="cursor-pointer select-none">Advanced: raw headers &amp; HTML body (enables SPF/DKIM/DMARC and link checks)</summary>
                <textarea
                  className="w-full mt-2 border border-line rounded-lg px-3 py-2 text-xs h-20 resize-none font-mono-ui placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                  placeholder="Paste raw email headers (From, Return-Path, Authentication-Results…)"
                  value={email.raw_headers}
                  onChange={(e) => setEmail({ ...email, raw_headers: e.target.value })}
                />
                <textarea
                  className="w-full mt-2 border border-line rounded-lg px-3 py-2 text-xs h-20 resize-none font-mono-ui placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
                  placeholder="Paste the HTML body (finds mismatched links and password forms)"
                  value={email.html_body}
                  onChange={(e) => setEmail({ ...email, html_body: e.target.value })}
                />
              </details>
              <button
                onClick={runEmailCheck}
                disabled={loading}
                className="w-full bg-navy text-white rounded-lg py-2.5 text-sm font-semibold flex items-center justify-center gap-2 shadow-card hover:bg-navy-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                Analyze Email
              </button>
            </>
          )}
          {error && <p className="text-xs text-danger">Error: {error}</p>}
        </div>
      </Panel>

      <Panel title="Verdict">
        {!result ? (
          <div className="p-8 text-center text-sm text-slate">
            Run a check to see the fused verdict and per-signal breakdown.
          </div>
        ) : (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
              <Badge verdict={result.verdict} />
              <span className="text-sm text-slate">
                {Math.round(result.confidence * 100)}% confidence
              </span>
              {result.confidence_detail && (
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                  result.confidence_detail.level === "high" ? "bg-emerald-100 text-emerald-700"
                  : result.confidence_detail.level === "medium" ? "bg-amber-100 text-amber-700"
                  : "bg-red-100 text-danger"
                }`}>
                  {result.confidence_detail.level} certainty
                </span>
              )}
            </div>

            <p className="text-sm text-slate">{result.explanation}</p>

            {result.confidence_detail?.note && (
              <p className="text-xs text-slate bg-gray-50 rounded-lg p-2.5">{result.confidence_detail.note}</p>
            )}
            {result.override && (
              <p className="text-xs px-2.5 py-1.5 rounded-md bg-navy text-white inline-block">
                Decided by your organisation's {result.override}
              </p>
            )}

            {result.authentication && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">Email Authentication</div>
                <div className="flex gap-2">
                  {["spf", "dkim", "dmarc"].map((k) => {
                    const v = result.authentication[k] || "none";
                    const good = v === "pass";
                    return (
                      <span key={k} className={`text-[11px] font-semibold px-2.5 py-1 rounded-full uppercase ${good ? "bg-emerald-100 text-emerald-700" : v === "none" ? "bg-gray-100 text-slate" : "bg-red-100 text-danger"}`}>
                        {k}: {v}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            <div>
              <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">
                Signal Breakdown
              </div>
              <div className="space-y-2">
                {Object.entries(result.breakdown).map(([key, value]) => (
                  <SignalBar key={key} label={SIGNAL_LABELS[key] || key} value={value} />
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">
                Top Reasons
              </div>
              <ul className="text-sm space-y-1 list-disc list-inside text-slate">
                {result.top_reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>

            {result.analyzed_urls?.length > 0 && !result.storyline && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">
                  Links scanned ({result.analyzed_urls.length})
                </div>
                <ul className="text-xs text-slate space-y-0.5 font-mono-ui">
                  {result.analyzed_urls.map((u) => <li key={u} className="truncate">{u}</li>)}
                </ul>
              </div>
            )}

            {result.storyline?.steps?.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">
                  Attack Storyline
                </div>
                <p className="text-xs text-slate mb-2">{result.storyline.narrative}</p>
                <ol className="space-y-1.5">
                  {result.storyline.steps.map((s) => (
                    <li key={s.step} className={`text-xs rounded-lg px-2.5 py-2 border ${
                      s.step === result.storyline.payload_step ? "border-danger/40 bg-red-50" : "border-line bg-gray-50"
                    }`}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono-ui truncate">{s.step}. {s.host || s.url}</span>
                        <Badge verdict={s.verdict} compact />
                      </div>
                      <div className="text-slate mt-0.5">{s.role_label}</div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {result.counterfactual?.scenarios?.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate font-medium mb-2">
                  What Would Change This Verdict
                </div>
                <ul className="text-xs text-slate space-y-1.5">
                  {result.counterfactual.scenarios.map((s) => (
                    <li key={s.signal} className="bg-gray-50 rounded-lg px-2.5 py-2">
                      {s.explanation}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.evidence_graph?.nodes?.length > 0 && (
              <details>
                <summary className="text-xs uppercase tracking-wide text-slate font-medium mb-2 cursor-pointer select-none">
                  Attack Evidence Graph ({result.evidence_graph.nodes.length} nodes)
                </summary>
                <div className="mt-2 space-y-2">
                  {Object.entries(SIGNAL_LABELS).map(([key]) => {
                    const sigKey = key.replace("_score", "");
                    const sigNode = result.evidence_graph.nodes.find((n) => n.id === `signal:${sigKey}`);
                    const reasons = result.evidence_graph.nodes.filter((n) => n.id.startsWith(`reason:${sigKey}:`));
                    if (!sigNode) return null;
                    return (
                      <div key={sigKey} className="text-xs">
                        <div className="flex justify-between font-medium text-slate">
                          <span>{sigNode.label}</span>
                          <span>contribution {Math.round(sigNode.contribution * 100)}%</span>
                        </div>
                        {reasons.length > 0 && (
                          <ul className="list-disc list-inside text-slate/80 mt-0.5 ml-2">
                            {reasons.map((r) => <li key={r.id}>{r.label}</li>)}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                </div>
              </details>
            )}

            <div className="pt-2 border-t border-line flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate mr-1">Was this verdict correct?</span>
              <button
                onClick={() => sendFeedback(true)}
                disabled={feedbackSent}
                className="p-1.5 rounded-lg hover:bg-emerald-50 text-emerald-600 transition-colors disabled:opacity-40"
                title="Confirm correct"
              >
                <ThumbsUp size={15} />
              </button>
              <button
                onClick={() => sendFeedback(false)}
                disabled={feedbackSent}
                className="p-1.5 rounded-lg hover:bg-red-50 text-danger transition-colors disabled:opacity-40"
                title="Report incorrect"
              >
                <ThumbsDown size={15} />
              </button>
              {feedbackSent && <span className="text-xs text-emerald-600">Thanks — logged for retraining.</span>}
              <button
                onClick={flagForReview}
                disabled={flagSent}
                className="ml-auto text-xs px-2.5 py-1.5 rounded-lg border border-line text-slate font-medium hover:bg-gray-50 hover:text-ink transition-colors disabled:opacity-40"
                title="Send to the analyst review queue for a second look"
              >
                {flagSent ? "Flagged for review" : "Flag for review"}
              </button>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function SignalBar({ label, value }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "bg-danger" : pct >= 30 ? "bg-amber" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-xs text-slate mb-1">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
