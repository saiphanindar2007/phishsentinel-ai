# PhishSentinel AI

A multi-signal, explainable phishing detection system: URL analysis + NLP
content classification + visual brand-impersonation detection + sender
reputation graph + email authentication (SPF/DKIM/DMARC) + HTML
link/form analysis, fused into one confidence score with a plain-language
explanation — delivered through a FastAPI backend, a React analyst
dashboard, and a Chrome extension that protects every page the user
visits in real time.

```
phishsentinel-ai/
├── backend/
│   ├── app/
│   │   ├── models/         url_analyzer, nlp_classifier, visual_detector,
│   │   │                   reputation_graph, email_headers, html_analysis,
│   │   │                   url_extract, fusion_engine, shap_explainer
│   │   ├── services/       cache, metrics, events (SSE), lists (allow/deny),
│   │   │                   csvsafe, runtime (shared singletons)
│   │   ├── routers/        analyze, feedback, lists, events, admin, system
│   │   ├── security.py     API key + admin key auth, IP rate limiting
│   │   ├── middleware.py   request id, security headers, metrics, 413
│   │   ├── logging_config.py  JSON structured logging
│   │   ├── config.py       env config + startup validation (fail-closed in prod)
│   │   └── main.py
│   ├── tests/               pytest suite incl. pure-logic + security tests
│   ├── training/            scripts to upgrade heuristics -> trained models
│   ├── Dockerfile
│   ├── requirements.txt     runtime deps
│   ├── requirements-ml.txt  + training-only deps (torch, transformers)
│   └── requirements-dev.txt + test deps (pytest, httpx)
├── extension/               Chrome extension (Manifest V3) + options page
├── dashboard/
│   ├── src/                 React dashboard — Overview, Live Feed, Analyzer,
│   │                        Batch Scan, History, Analytics, Allow/Deny, System, Settings
│   ├── Dockerfile / nginx.conf
│   └── legacy/index.html    zero-build single-file fallback dashboard
├── docker-compose.yml        Postgres + backend + nginx-served dashboard
└── .github/workflows/ci.yml  tests + both Docker builds on every push
```

## Quickstart (local development)

**1. Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open `http://localhost:8000/docs` for interactive API docs (disabled by
default once `ENVIRONMENT=production`).

**2. Dashboard**
```bash
cd dashboard
npm install
npm run dev
```
Open `http://localhost:5173`. In **Settings**, point it at
`http://localhost:8000`; add the API key and admin key if you set them.

**3. Chrome extension**
`chrome://extensions` → enable Developer Mode → **Load unpacked** →
select `extension/`. On first install its Options page opens — set the
server URL and (if required) the API key there.

**Or bring everything up with Docker in one command:**
```bash
cp .env.example .env        # set POSTGRES_PASSWORD, API_KEY, ADMIN_API_KEY
docker compose up --build -d
# Dashboard: http://localhost:8080  (talks to the API through nginx's /api proxy)
```

## Production features

- **Fail-closed config** — `ENVIRONMENT=production` refuses to boot
  without real `API_KEY`/`ADMIN_API_KEY` values and explicit CORS origins.
- **Two-tier auth** — a client `API_KEY` for `/analyze`, `/feedback`,
  `/events`; a separate `ADMIN_API_KEY` for `/lists`, `/admin`,
  `/system`, `/metrics`. Constant-time comparison, brute-force throttling.
- **IP-keyed rate limiting**, bounded and pruned — never grows unbounded,
  never bypassable by spoofing the API key header.
- **Allow/deny lists** — organization overrides that beat the model,
  applied instantly and fully audited.
- **Live Feed** — every verdict streamed to the dashboard over SSE
  (bounded per-subscriber queues, a hard subscriber cap).
- **Batch Scan** — up to 100 URLs per call, CSV export.
- **TTL+LRU verdict cache**, JSON structured logs with request IDs,
  Prometheus metrics, security headers, a request-size cap, and an
  audit log for every admin action.
- **Email authentication** — SPF/DKIM/DMARC parsing, Return-Path/
  Reply-To mismatch, display-name spoofing and punycode detection; HTML
  link/form analysis (mismatched hrefs, password forms over HTTP).
- **Data retention** — optional automatic purge of old verdicts/feedback.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

See `backend/tests/TESTING_GUIDE.md` for the full automated + manual
checklist.

## Retraining the models

The system runs on transparent heuristics out of the box. See
`backend/training/README.md` to train real URL/NLP models from
collected and exported feedback, then hot-swap them in with
`POST /admin/reload-models` — no restart needed.

## Scaling beyond one process

The rate limiter, cache, allow/deny-list cache and live-feed bus are
in-process by design (`--workers 1` in the Dockerfile). To run more than
one worker or instance, swap those for shared backends with the same
interface (Redis is the natural choice for all four) and put a database
connection pool in front of Postgres.
