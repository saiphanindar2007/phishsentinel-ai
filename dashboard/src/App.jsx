import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import Sidebar, { TABS } from "./components/Sidebar.jsx";
import { usePolling } from "./lib/usePolling.js";
import { api } from "./lib/api.js";

import OverviewTab from "./tabs/OverviewTab.jsx";
import LiveTab from "./tabs/LiveTab.jsx";
import AnalyzerTab from "./tabs/AnalyzerTab.jsx";
import BatchTab from "./tabs/BatchTab.jsx";
import HistoryTab from "./tabs/HistoryTab.jsx";
import AnalyticsTab from "./tabs/AnalyticsTab.jsx";
import ReviewTab from "./tabs/ReviewTab.jsx";
import ListsTab from "./tabs/ListsTab.jsx";
import SystemTab from "./tabs/SystemTab.jsx";
import SettingsTab from "./tabs/SettingsTab.jsx";

const PANELS = {
  overview: OverviewTab,
  live: LiveTab,
  analyzer: AnalyzerTab,
  batch: BatchTab,
  history: HistoryTab,
  analytics: AnalyticsTab,
  review: ReviewTab,
  lists: ListsTab,
  system: SystemTab,
  settings: SettingsTab,
};

const DESCRIPTIONS = {
  overview: "Fleet-wide verdict activity at a glance",
  live: "Every verdict the moment it's scored",
  analyzer: "Run a single URL or email through every signal",
  batch: "Scan up to 100 URLs in one pass",
  history: "Search and export past verdicts",
  review: "Low-confidence verdicts awaiting an analyst",
  analytics: "Verdict mix and signal strength over time",
  lists: "Organization allow / deny overrides",
  system: "Health, cache, model and audit status",
  settings: "Connection and credentials for this browser",
};

const initialTab = () => {
  const h = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === h) ? h : "overview";
};

export default function App() {
  const [active, setActive] = useState(initialTab);
  const [navOpen, setNavOpen] = useState(false);
  const { data: health, error } = usePolling(() => api.health(), 10000);
  const apiOk = !!health && !error;
  const Active = PANELS[active];
  const current = TABS.find((t) => t.id === active) || TABS[0];

  useEffect(() => {
    window.location.hash = active;
  }, [active]);

  return (
    <div className="min-h-screen bg-surface lg:flex">
      <Sidebar active={active} onChange={setActive} open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-white/80 px-4 py-3 backdrop-blur lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => setNavOpen(true)}
              className="rounded-lg p-1.5 text-slate hover:bg-gray-100 hover:text-ink lg:hidden"
              aria-label="Open menu"
            >
              <Menu size={18} />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold text-ink leading-tight">{current.label}</h1>
              <p className="hidden truncate text-xs text-slate sm:block">{DESCRIPTIONS[active]}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {health?.version && <span className="hidden font-mono-ui text-[11px] text-slate md:inline">v{health.version}</span>}
            <StatusPillDark connected={apiOk} label={apiOk ? "API connected" : "API unreachable"} />
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 lg:px-8">
          <div key={active} className="animate-fade-in">
            <Active />
          </div>
        </main>
      </div>
    </div>
  );
}

// Light-background variant of StatusPill for the (white) top header bar.
function StatusPillDark({ connected, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
        connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-danger"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-danger"}`} />
      {label}
    </span>
  );
}
