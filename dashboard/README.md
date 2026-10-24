# PhishSentinel AI — Analyst Dashboard

React 18 + Vite + Tailwind + Recharts single-page app for the PhishSentinel
REST API (the same API the Chrome extension uses).

| Tab | What it does |
|---|---|
| **Overview** | KPI cards, 24-hour verdict timeline, top flagged domains, recent verdicts, API/DB status |
| **Live Feed** | Real-time stream of every verdict (Server-Sent Events over `fetch`, auto-reconnect, pause / flagged-only) |
| **Analyzer** | URL or email check; email mode accepts raw headers (SPF/DKIM/DMARC panel) and HTML body (link/form tricks); per-signal breakdown; feedback buttons |
| **Batch Scan** | Paste or load up to 100 URLs, worst-first results, CSV download (formula-injection safe) |
| **History** | Server-side pagination, search and verdict filters, audited CSV export |
| **Analytics** | Verdict mix and average signal strength |
| **Allow / Deny** | Admin CRUD for organisation allowlist / denylist (applied instantly, audited) |
| **System** | Health, model state, cache and rule stats, model reload, retention purge, raw Prometheus metrics, audit log |
| **Settings** | API base URL, API key, Admin key (stored only in this browser) |

Admin-only tabs (Allow / Deny, System) need the **Admin key** in Settings
when the backend sets `ADMIN_API_KEY`.

## Run it

```bash
cd dashboard
npm install
npm run dev
```

Open **http://localhost:5173**. By default it talks to
`http://localhost:8000` (your local FastAPI backend) — change this
anytime from the **Settings** tab, or set `VITE_API_BASE` in `.env`
before building (copy `.env.example` to `.env` first) to bake in a
different default.

**Build for deployment:**
```bash
npm run build   # outputs dashboard/dist — deploy as a static site
                # (Vercel, Netlify, GitHub Pages, Render static site, etc.)
```

## No-build fallback

`dashboard/legacy/index.html` is the original zero-dependency,
single-file dashboard — no `npm install`, no build step, just open it
in a browser. Keep it as your emergency fallback for a live demo if
Node/npm isn't available on the presentation machine; it talks to the
same backend API.

## Why React + Vite + Tailwind here specifically

- **Vite** — sub-second dev server startup and hot reload, important
  when you're iterating on the dashboard right up to a demo.
- **Tailwind** — utility classes keep the four-signal breakdown bars,
  status pills, and badges consistent without a separate CSS file per
  component.
- **Recharts** — the Analytics tab's charts are SVG, no canvas/WebGL
  dependency, and render fine even on modest machines.
- **lucide-react** — lightweight icon set (no icon font, no large
  sprite sheet) for the tab bar and status indicators.

Every one of these is a free, open-source package — no change to the
project's ₹0 software budget.
