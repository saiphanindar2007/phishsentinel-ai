import { LayoutDashboard, ScanSearch, Layers, Radio, History, BarChart3, ShieldCheck, Server, Settings, ClipboardCheck, ShieldHalf, X } from "lucide-react";

export const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      { id: "overview", label: "Overview", icon: LayoutDashboard },
      { id: "live", label: "Live Feed", icon: Radio },
    ],
  },
  {
    label: "Investigate",
    items: [
      { id: "analyzer", label: "Analyzer", icon: ScanSearch },
      { id: "batch", label: "Batch Scan", icon: Layers },
      { id: "history", label: "History", icon: History },
      { id: "review", label: "Review Queue", icon: ClipboardCheck },
      { id: "analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    label: "Govern",
    items: [
      { id: "lists", label: "Allow / Deny", icon: ShieldCheck },
      { id: "system", label: "System", icon: Server },
    ],
  },
];

export const TABS = NAV_GROUPS.flatMap((g) => g.items);

function NavButton({ item, active, onClick }) {
  const Icon = item.icon;
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`group flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors relative
        ${active ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white"}`}
    >
      {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-teal" />}
      <Icon size={16} className={active ? "text-teal-light" : "text-white/40 group-hover:text-white/80"} />
      {item.label}
    </button>
  );
}

export default function Sidebar({ active, onChange, open, onClose }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 shrink-0 flex-col bg-navy transition-transform duration-200 lg:static lg:translate-x-0
          ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between gap-2 px-5 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal/15 text-teal-light">
              <ShieldHalf size={17} />
            </span>
            <div>
              <div className="text-sm font-bold text-white leading-tight">PhishSentinel AI</div>
              <div className="text-[11px] text-white/45 leading-tight">Analyst Console</div>
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-white/50 hover:bg-white/10 hover:text-white lg:hidden" aria-label="Close menu">
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4" role="tablist">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-4">
              <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-white/35">{group.label}</div>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavButton key={item.id} item={item} active={item.id === active} onClick={() => { onChange(item.id); onClose(); }} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-3 pb-3">
          <NavButton item={{ id: "settings", label: "Settings", icon: Settings }} active={active === "settings"}
            onClick={() => { onChange("settings"); onClose(); }} />
        </div>
      </aside>
    </>
  );
}
