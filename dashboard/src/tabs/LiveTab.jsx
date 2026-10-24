import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import Panel from "../components/Panel.jsx";
import Badge from "../components/Badge.jsx";
import { Pause, Play, Trash2 } from "lucide-react";

const MAX_ROWS = 200;

export default function LiveTab() {
  const [events, setEvents] = useState([]);
  const [state, setState] = useState({ s: "connecting", msg: "" });
  const [paused, setPaused] = useState(false);
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  useEffect(() => {
    const stop = api.streamVerdicts(
      (ev) => {
        if (pausedRef.current) return;
        setEvents((prev) => [{ ...ev, _t: Date.now() }, ...prev].slice(0, MAX_ROWS));
      },
      (s, msg) => setState({ s, msg: msg || "" }),
    );
    return stop;
  }, []);

  const shown = onlyFlagged ? events.filter((e) => e.verdict !== "safe") : events;
  const dot = state.s === "live" ? "bg-emerald-500" : state.s === "connecting" ? "bg-amber" : "bg-danger";

  return (
    <Panel
      title={`Live Feed (${shown.length})`}
      right={
        <div className="flex items-center gap-3 text-xs text-slate">
          <span className="flex items-center gap-1.5">
            <span className={`relative flex h-2 w-2`}>
              {state.s === "live" && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${dot} opacity-60`} />}
              <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
            </span>
            {state.s === "live" ? "Streaming" : state.s === "connecting" ? "Connecting…" : `Reconnecting${state.msg ? ` (${state.msg})` : ""}`}
          </span>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} /> flagged only
          </label>
          <button onClick={() => setPaused((p) => !p)} className="flex items-center gap-1 hover:text-ink">
            {paused ? <Play size={13} /> : <Pause size={13} />} {paused ? "Resume" : "Pause"}
          </button>
          <button onClick={() => setEvents([])} className="flex items-center gap-1 hover:text-ink">
            <Trash2 size={13} /> Clear
          </button>
        </div>
      }
    >
      {!shown.length ? (
        <div className="p-8 text-center text-sm text-slate">
          Waiting for activity… every URL the browser extension checks and every scan you run appears here instantly.
        </div>
      ) : (
        <ul className="divide-y divide-line max-h-[560px] overflow-y-auto">
          {shown.map((e) => (
            <li key={e.verdict_id + e._t} className="px-4 py-2.5 flex items-start gap-3 text-sm hover:bg-gray-50/70 transition-colors">
              <Badge verdict={e.verdict} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-ink">{e.raw_input}</div>
                <div className="text-xs text-slate truncate">
                  {e.override ? `[${e.override}] ` : ""}{e.explanation}
                </div>
              </div>
              <div className="text-right shrink-0 text-xs text-slate">
                <div>{Math.round(e.confidence * 100)}%</div>
                <div>{new Date(e._t).toLocaleTimeString()}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
