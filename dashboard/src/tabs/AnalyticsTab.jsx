import { useMemo } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import { usePolling } from "../lib/usePolling.js";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";

const VERDICT_COLORS = { safe: "#10B981", suspicious: "#D97706", phishing: "#DC2626" };

export default function AnalyticsTab() {
  const { data: verdicts } = usePolling(() => api.verdicts(200), 20000);

  const pieData = useMemo(() => {
    if (!verdicts?.length) return [];
    const counts = { safe: 0, suspicious: 0, phishing: 0 };
    verdicts.forEach((v) => { counts[v.verdict] = (counts[v.verdict] || 0) + 1; });
    return Object.entries(counts)
      .filter(([, count]) => count > 0)
      .map(([name, value]) => ({ name, value }));
  }, [verdicts]);

  const avgSignalData = useMemo(() => {
    if (!verdicts?.length) return [];
    const sums = { url: 0, nlp: 0, visual: 0, reputation: 0 };
    let n = 0;
    verdicts.forEach((v) => {
      if (!v.breakdown) return;
      sums.url += v.breakdown.url_score || 0;
      sums.nlp += v.breakdown.nlp_score || 0;
      sums.visual += v.breakdown.visual_score || 0;
      sums.reputation += v.breakdown.reputation_score || 0;
      n += 1;
    });
    if (!n) return [];
    return [
      { signal: "URL", avg: +(sums.url / n * 100).toFixed(1) },
      { signal: "NLP", avg: +(sums.nlp / n * 100).toFixed(1) },
      { signal: "Visual", avg: +(sums.visual / n * 100).toFixed(1) },
      { signal: "Reputation", avg: +(sums.reputation / n * 100).toFixed(1) },
    ];
  }, [verdicts]);

  const inputTypeData = useMemo(() => {
    if (!verdicts?.length) return [];
    const counts = {};
    verdicts.forEach((v) => { counts[v.input_type] = (counts[v.input_type] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [verdicts]);

  if (!verdicts?.length) {
    return (
      <Panel title="Analytics">
        <div className="p-8 text-center text-sm text-slate">
          Not enough data yet — run a few checks in the Analyzer tab first.
        </div>
      </Panel>
    );
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      <Panel title="Verdict Distribution">
        <div className="p-4" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={VERDICT_COLORS[entry.name] || "#64748B"} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel title="Average Signal Contribution">
        <div className="p-4" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={avgSignalData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="signal" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="avg" fill="#0EA5A8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="px-4 pb-4 text-xs text-slate">
          Which of the four fusion signals (URL, NLP, Visual, Sender
          Reputation) is contributing the most across everything analyzed
          so far — useful for spotting whether one channel is dominating
          verdicts more than intended.
        </p>
      </Panel>

      <Panel title="Checks by Input Type" className="md:col-span-2">
        <div className="p-4" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={inputTypeData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 12 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={80} />
              <Tooltip />
              <Bar dataKey="value" fill="#0A1526" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}
