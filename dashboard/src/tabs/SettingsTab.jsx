import { useState } from "react";
import { getApiBase, setApiBase, getApiKey, setApiKey, getAdminKey, setAdminKey, api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import { CheckCircle2, XCircle } from "lucide-react";

export default function SettingsTab() {
  const [base, setBase] = useState(getApiBase());
  const [key, setKey] = useState(getApiKey());
  const [adminKey, setAdmin] = useState(getAdminKey());
  const [testResult, setTestResult] = useState(null); // null | "ok" | "fail"
  const [saved, setSaved] = useState(false);

  function save() {
    setApiBase(base);
    setApiKey(key);
    setAdminKey(adminKey);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function testConnection() {
    setApiBase(base);
    setApiKey(key);
    setAdminKey(adminKey);
    try {
      await api.health();
      setTestResult("ok");
    } catch {
      setTestResult("fail");
    }
  }

  return (
    <Panel title="Connection Settings">
      <div className="p-4 space-y-4 max-w-lg">
        <div>
          <label className="text-xs font-medium text-slate">Backend API Base URL</label>
          <input
            className="w-full mt-1.5 border border-line rounded-lg px-3 py-2 text-sm placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="http://localhost:8000"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate">
            API Key <span className="text-slate/70">(only needed if the backend sets API_KEY)</span>
          </label>
          <input
            className="w-full mt-1.5 border border-line rounded-lg px-3 py-2 text-sm placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Leave blank in dev/demo mode"
            type="password"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate">
            Admin Key <span className="text-slate/70">(operators only: lists, audit log, system, purge)</span>
          </label>
          <input
            className="w-full mt-1.5 border border-line rounded-lg px-3 py-2 text-sm placeholder:text-slate/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-teal/50 focus:border-teal"
            value={adminKey}
            onChange={(e) => setAdmin(e.target.value)}
            placeholder="ADMIN_API_KEY from the backend"
            type="password"
            autoComplete="off"
          />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={save} className="bg-navy text-white rounded-lg px-4 py-2 text-sm font-semibold shadow-card hover:bg-navy-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal">
            Save
          </button>
          <button
            onClick={testConnection}
            className="border border-line rounded-lg px-4 py-2 text-sm font-semibold text-ink hover:bg-gray-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy"
          >
            Test Connection
          </button>
          {saved && <span className="text-xs text-emerald-600">Saved.</span>}
          {testResult === "ok" && (
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <CheckCircle2 size={14} /> Reachable
            </span>
          )}
          {testResult === "fail" && (
            <span className="flex items-center gap-1 text-xs text-danger">
              <XCircle size={14} /> Unreachable
            </span>
          )}
        </div>

        <p className="text-xs text-slate pt-3 border-t border-line">
          Settings are stored locally in this browser only (
          <code className="bg-gray-100 px-1 rounded">localStorage</code>) — nothing is sent anywhere
          except the API base URL you configure here.
        </p>
      </div>
    </Panel>
  );
}
