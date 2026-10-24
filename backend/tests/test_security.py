"""
Security tests for Phase 7 — these exercise app/security.py directly
(not through the shared `client` fixture, which runs with auth/rate
limiting deliberately disabled for the rest of the suite — see
conftest.py). Each test spins up its own isolated TestClient with the
specific security settings it needs.
"""
import importlib
import os


def _fresh_app_with_env(**env_overrides):
    """Reloads app.config -> app.security -> the routers -> app.main with
    different env vars set, so each test gets a clean app instance
    reflecting its own API_KEY / RATE_LIMIT_PER_MINUTE. Order matters:
    each router does `from app.security import rate_limit,
    require_api_key`, which BINDS those function objects at import time —
    reloading app.security alone creates new function objects that the
    already-imported routers don't see, so the routers must be reloaded
    too (picking up the new functions), then app.main (picking up the
    freshly reloaded routers), in that dependency order."""
    from fastapi.testclient import TestClient

    old_env = {k: os.environ.get(k) for k in env_overrides}
    os.environ.update(env_overrides)
    try:
        import app.config
        import app.security
        import app.services.runtime
        import app.routers.analyze
        import app.routers.feedback
        import app.routers.lists
        import app.routers.events
        import app.routers.admin
        import app.routers.system
        import app.main

        importlib.reload(app.config)
        importlib.reload(app.security)
        importlib.reload(app.services.runtime)
        importlib.reload(app.routers.analyze)
        importlib.reload(app.routers.feedback)
        importlib.reload(app.routers.lists)
        importlib.reload(app.routers.events)
        importlib.reload(app.routers.admin)
        importlib.reload(app.routers.system)
        importlib.reload(app.main)
        return TestClient(app.main.app)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_request_without_api_key_is_rejected_when_key_is_set():
    client = _fresh_app_with_env(API_KEY="test-secret-123", RATE_LIMIT_ENABLED="false")
    resp = client.post("/analyze/url", json={"url": "https://example.com"})
    assert resp.status_code == 401


def test_request_with_correct_api_key_is_accepted():
    client = _fresh_app_with_env(API_KEY="test-secret-123", RATE_LIMIT_ENABLED="false")
    resp = client.post(
        "/analyze/url",
        json={"url": "https://example.com"},
        headers={"X-API-Key": "test-secret-123"},
    )
    assert resp.status_code == 200


def test_request_with_wrong_api_key_is_rejected():
    client = _fresh_app_with_env(API_KEY="test-secret-123", RATE_LIMIT_ENABLED="false")
    resp = client.post(
        "/analyze/url",
        json={"url": "https://example.com"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_no_api_key_configured_means_auth_is_open():
    # This is the documented dev/demo default — confirm it stays that way.
    client = _fresh_app_with_env(API_KEY="", RATE_LIMIT_ENABLED="false")
    resp = client.post("/analyze/url", json={"url": "https://example.com"})
    assert resp.status_code == 200


def test_rate_limit_blocks_after_threshold_is_exceeded():
    client = _fresh_app_with_env(API_KEY="", RATE_LIMIT_ENABLED="true", RATE_LIMIT_PER_MINUTE="3")
    statuses = [
        client.post("/analyze/url", json={"url": "https://example.com"}).status_code
        for _ in range(5)
    ]
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_rate_limit_disabled_allows_unlimited_requests():
    client = _fresh_app_with_env(API_KEY="", RATE_LIMIT_ENABLED="false", RATE_LIMIT_PER_MINUTE="1")
    statuses = [
        client.post("/analyze/url", json={"url": "https://example.com"}).status_code
        for _ in range(5)
    ]
    assert all(s == 200 for s in statuses)


def test_admin_endpoint_rejects_api_key_only():
    client = _fresh_app_with_env(API_KEY="client-key", ADMIN_API_KEY="admin-key", RATE_LIMIT_ENABLED="false")
    resp = client.get("/system/info", headers={"X-Admin-Key": "client-key"})
    assert resp.status_code == 403


def test_admin_endpoint_accepts_correct_admin_key():
    client = _fresh_app_with_env(API_KEY="client-key", ADMIN_API_KEY="admin-key", RATE_LIMIT_ENABLED="false")
    resp = client.get("/system/info", headers={"X-Admin-Key": "admin-key"})
    assert resp.status_code == 200


def test_admin_endpoints_disabled_in_production_without_admin_key():
    client = _fresh_app_with_env(API_KEY="client-key", ADMIN_API_KEY="", ENVIRONMENT="production",
                                 CORS_ORIGINS="https://example.com", RATE_LIMIT_ENABLED="false")
    resp = client.get("/system/info")
    assert resp.status_code == 403
