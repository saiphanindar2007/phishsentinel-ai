def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_url_endpoint_returns_verdict_shape(client):
    resp = client.post("/analyze/url", json={"url": "http://paypa1-verify-account.tk/login"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in ("safe", "suspicious", "phishing")
    assert 0.0 <= body["confidence"] <= 1.0
    assert "breakdown" in body
    assert "top_reasons" in body


def test_analyze_email_endpoint_runs_all_four_signals(client):
    resp = client.post(
        "/analyze/email",
        json={
            "sender": "security@paypa1-alerts.tk",
            "subject": "Urgent: verify your account now",
            "body": "Click the link below and confirm your password immediately or your account will be suspended.",
            "url": "http://paypa1-alerts.tk/verify",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["breakdown"]["nlp_score"] > 0


def test_verdicts_and_stats_endpoints(client):
    client.post("/analyze/url", json={"url": "https://example.com"})
    resp = client.get("/analyze/verdicts?limit=5")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert "breakdown" in rows[0]

    resp = client.get("/analyze/stats")
    assert resp.status_code == 200
    assert "total" in resp.json()


def test_admin_reload_models_endpoint_reports_status(client):
    resp = client.post("/admin/reload-models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model_loaded_now" in body


def test_feedback_roundtrip(client):
    verdict = client.post("/analyze/url", json={"url": "https://example.com"}).json()
    resp = client.post(
        "/feedback",
        json={"verdict_id": verdict["verdict_id"], "is_correct": True, "source": "web"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
