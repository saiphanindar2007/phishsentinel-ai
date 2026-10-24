import { useCallback, useEffect, useState } from "react";
import { api, getAdminKey } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import { Plus, Trash2 } from "lucide-react";

export default function ListsTab() {
  const [entries, setEntries] = useState([]);
  const [kind, setKind] = useState("deny");
  const [domain, setDomain] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setEntries(await api.lists()); setError(null); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function add() {
    if (!domain.trim()) return;
    setBusy(true);
    try {
      await api.addListEntry({ kind, domain: domain.trim(), note: note.trim() || undefined });
      setDomain(""); setNote("");
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function remove(e) {
    if (!window.confirm(`Remove ${e.domain} from the ${e.kind}list?`)) return;
    try { await api.deleteListEntry(e.id); await load(); } catch (err) { setError(err.message); }
  }

  const groups = { deny: entries.filter((e) => e.kind === "deny"), allow: entries.filter((e) => e.kind === "allow") };

  return (
    <div>
      <Panel title="Add a rule">
        <div className="p-4 flex flex-wrap gap-2 items-center">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal">
            <option value="deny">Always block (denylist)</option>
            <option value="allow">Never flag (allowlist)</option>
          </select>
          <input className="flex-1 min-w-[200px] border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal" placeholder="example.com (covers subdomains)"
            value={domain} onChange={(e) => setDomain(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
          <input className="flex-1 min-w-[160px] border border-line rounded-lg px-3 py-2 text-sm transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal" placeholder="Note (optional)"
            value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          <button onClick={add} disabled={busy} className="bg-navy text-white rounded-lg px-4 py-2 text-sm font-semibold shadow-card hover:bg-navy-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal flex items-center gap-1.5 disabled:opacity-60">
            <Plus size={14} /> Add
          </button>
        </div>
        {error && (
          <p className="px-4 pb-3 text-xs text-danger">
            {error}{!getAdminKey() && " — set the Admin key in Settings if the backend requires one."}
          </p>
        )}
        <p className="px-4 pb-4 text-xs text-slate">
          Denylist beats allowlist. Matches are shown in the verdict explanation, and every change is written to the audit log.
        </p>
      </Panel>

      <div className="grid md:grid-cols-2 gap-5">
        {["deny", "allow"].map((k) => (
          <Panel key={k} title={`${k === "deny" ? "Denylist" : "Allowlist"} (${groups[k].length})`}>
            {!groups[k].length ? (
              <div className="p-6 text-center text-sm text-slate">No entries.</div>
            ) : (
              <ul className="divide-y divide-line">
                {groups[k].map((e) => (
                  <li key={e.id} className="px-4 py-2.5 flex items-center justify-between text-sm hover:bg-gray-50/70 transition-colors">
                    <div className="min-w-0">
                      <div className="text-ink font-medium truncate">{e.domain}</div>
                      <div className="text-xs text-slate truncate">{e.note || "—"} · {e.created_by}</div>
                    </div>
                    <button onClick={() => remove(e)} className="p-1.5 rounded-lg text-slate hover:text-danger hover:bg-red-50 transition-colors" aria-label={`Remove ${e.domain}`}>
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}
