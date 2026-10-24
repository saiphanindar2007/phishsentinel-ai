// PhishSentinel AI — API client
// --------------------------------
// Every request goes through here so the base URL, API key and admin key
// from the Settings tab apply everywhere. Admin-only endpoints (lists,
// audit, metrics, purge, model reload) send X-Admin-Key.

const LS = { base: "phishsentinel_api_base", key: "phishsentinel_api_key", admin: "phishsentinel_admin_key" };

const read = (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } };

export const getApiBase = () => read(LS.base) || import.meta.env.VITE_API_BASE || "http://localhost:8000";
export const setApiBase = (url) => write(LS.base, url.trim().replace(/\/+$/, ""));
export const getApiKey = () => read(LS.key);
export const setApiKey = (k) => write(LS.key, k.trim());
export const getAdminKey = () => read(LS.admin);
export const setAdminKey = (k) => write(LS.admin, k.trim());

function headers({ admin = false, json = true } = {}) {
  const key = getApiKey();
  const adminKey = getAdminKey();
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(key ? { "X-API-Key": key } : {}),
    ...(admin && adminKey ? { "X-Admin-Key": adminKey } : {}),
  };
}

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || detail);
    } catch { /* non-JSON error body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

const url = (path, params) => {
  const qs = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && qs.set(k, v));
  const s = qs.toString();
  return `${getApiBase()}${path}${s ? `?${s}` : ""}`;
};

const get = (path, params, opts) => fetch(url(path, params), { headers: headers(opts) }).then(handle);
const send = (method, path, body, opts) =>
  fetch(url(path), { method, headers: headers(opts), body: body === undefined ? undefined : JSON.stringify(body) }).then(handle);

export const api = {
  health: () => fetch(url("/health")).then(handle),
  ready: () => fetch(url("/health/ready")).then(async (r) => ({ ok: r.ok, ...(await r.json().catch(() => ({}))) })),
  stats: () => get("/analyze/stats"),
  timeline: (hours = 24) => get("/analyze/timeline", { hours }),
  topDomains: (limit = 8) => get("/analyze/top-domains", { limit }),
  verdicts: (limit = 50) => get("/analyze/verdicts", { limit }),

  // Paginated history: returns { rows, total } (total comes from X-Total-Count).
  async verdictsPage({ limit = 25, offset = 0, verdict, q } = {}) {
    const res = await fetch(url("/analyze/verdicts", { limit, offset, verdict: verdict === "all" ? "" : verdict, q }), { headers: headers() });
    const rows = await handle(res);
    return { rows, total: Number(res.headers.get("X-Total-Count") || rows.length) };
  },

  analyzeUrl: (u) => send("POST", "/analyze/url", { url: u }),
  analyzeEmail: (payload) => send("POST", "/analyze/email", payload),
  analyzeBatch: (urls) => send("POST", "/analyze/batch", { urls }),
  sendFeedback: (payload) => send("POST", "/feedback", payload),

  // Review queue (analyst feedback workflow)
  flagForReview: (payload) => send("POST", "/feedback/flag", payload),
  reviewQueue: (status) => get("/feedback/queue", { status }),
  reviewQueueSummary: () => get("/feedback/queue/summary"),
  resolveReview: (id, payload) => send("POST", `/feedback/queue/${id}/resolve`, payload, { admin: true }),

  // Reproducible evaluation bench
  runEvaluation: () => send("POST", "/eval/run", undefined, { admin: true }),
  evalRuns: (limit = 20) => get("/eval/runs", { limit }, { admin: true }),
  evalDataset: () => get("/eval/dataset", null, { admin: true }),

  // Downloads a CSV through fetch (so the API key header is sent) and saves it.
  async exportCsv({ verdict, q } = {}) {
    const res = await fetch(url("/analyze/export.csv", { verdict: verdict === "all" ? "" : verdict, q }), { headers: headers({ json: false }) });
    if (!res.ok) return handle(res);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "phishsentinel-verdicts.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  },

  // Admin
  lists: () => get("/lists", null, { admin: true }),
  addListEntry: (entry) => send("POST", "/lists", entry, { admin: true }),
  deleteListEntry: (id) => send("DELETE", `/lists/${id}`, undefined, { admin: true }),
  systemInfo: () => get("/system/info", null, { admin: true }),
  audit: (limit = 50) => get("/admin/audit", { limit }, { admin: true }),
  reloadModels: () => send("POST", "/admin/reload-models", undefined, { admin: true }),
  purge: (days) => fetch(url("/admin/purge", { days }), { method: "POST", headers: headers({ admin: true }) }).then(handle),
  async metricsText() {
    const res = await fetch(url("/metrics"), { headers: headers({ admin: true, json: false }) });
    if (!res.ok) return handle(res);
    return res.text();
  },

  /**
   * Live verdict stream. EventSource can't send headers, so this reads the
   * SSE response with fetch(). Returns a stop() function. Reconnects with
   * backoff; reports state via onState('connecting'|'live'|'error', msg).
   */
  streamVerdicts(onEvent, onState) {
    let stopped = false;
    let controller = null;
    let delay = 1000;

    async function run() {
      while (!stopped) {
        controller = new AbortController();
        onState?.("connecting");
        try {
          const res = await fetch(url("/events/stream"), { headers: headers({ json: false }), signal: controller.signal });
          if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.detail || res.statusText);
          }
          onState?.("live");
          delay = 1000;
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let idx;
            while ((idx = buf.indexOf("\n\n")) >= 0) {
              const frame = buf.slice(0, idx);
              buf = buf.slice(idx + 2);
              const data = frame.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
              if (data) { try { onEvent(JSON.parse(data)); } catch { /* ignore malformed frame */ } }
            }
          }
        } catch (err) {
          if (stopped) return;
          onState?.("error", err.message);
        }
        if (stopped) return;
        await new Promise((r) => setTimeout(r, delay));
        delay = Math.min(delay * 2, 15000);
      }
    }
    run();
    return () => { stopped = true; controller?.abort(); };
  },
};
