# PhishSentinel AI — Testing Guide

## 1. Automated tests (run in CI on every push)

```bash
pip install -r requirements-dev.txt
pytest -v
```

Covers:
- `test_fusion_engine.py` — weighted fusion, threshold edges, explanation text
- `test_url_analyzer.py` — heuristic + model-backed URL scoring
- `test_visual_detector.py` — brand/pHash comparison
- `test_services_pure.py` — cache TTL/eviction, metrics + path normalization,
  event bus backpressure/subscriber cap, allow/deny list matching and
  fail-safe reload, CSV-injection safety, URL extraction, SPF/DKIM/DMARC
  header analysis, HTML link/form analysis
- `test_security.py` — API-key auth, admin-key auth (including the
  production lockout when `ADMIN_API_KEY` is unset), and rate limiting
- `test_api.py` — end-to-end request/response shape through the live app

## 2. Manual / exploratory checks

- [ ] `uvicorn app.main:app --reload` boots cleanly with an empty `.env`
- [ ] Set `ENVIRONMENT=production` with no `API_KEY`/`ADMIN_API_KEY` — the
      app must refuse to start (see `app/config.py::validate_config`)
- [ ] `/docs` is served in development, 404s when `DOCS_ENABLED=false`
- [ ] Analyzer tab: a known-bad URL/email returns `phishing`; add it to
      the denylist and re-run — verdict flips to `phishing` with
      `override: "denylist"` even if the model would have said otherwise
- [ ] Live Feed tab shows the verdict the instant Analyzer/Batch submits it
- [ ] Batch Scan: paste 100+ URLs — extra ones are rejected with a 422,
      not silently truncated
- [ ] History: search + verdict filter narrow results; CSV export opens
      cleanly in Excel/Sheets (no `=`/`+`/`-`/`@` formula execution)
- [ ] Kill the database mid-demo — `/health/ready` returns 503 while
      `/health/live` still returns 200 (liveness vs readiness)
- [ ] `GET /metrics` without `X-Admin-Key` is refused; with the key it
      returns Prometheus text

## 3. Load testing

`training/load_test.py` hammers `/analyze/url` to check the rate
limiter, cache hit rate and p95 latency under concurrency.
