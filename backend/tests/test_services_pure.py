"""
Pure-logic tests for the new production modules: cache, metrics, event
bus, org lists, CSV safety, config validation, email headers, HTML
analysis and URL extraction. None of these import fastapi/sqlalchemy, so
they also serve as a fast, dependency-light smoke test.
"""
import time

from app.services.cache import TTLCache
from app.services.metrics import Metrics, normalize_path
from app.services.events import EventBus
from app.services.lists import ListMatcher, ListService, normalize_domain, host_of
from app.services.csvsafe import csv_safe, rows_to_csv
from app.models.url_extract import extract_urls
from app.models.email_headers import analyze_headers
from app.models.html_analysis import analyze_html


def test_cache_ttl_expiry_and_eviction():
    t = [0.0]
    c = TTLCache(ttl_seconds=10, max_entries=2, clock=lambda: t[0])
    c.set("a", 1)
    t[0] = 5
    assert c.get("a") == 1
    t[0] = 11
    assert c.get("a") is None
    c.set("a", 1); c.set("b", 2); c.set("c", 3)
    assert c.stats()["size"] <= 2


def test_metrics_counts_and_normalizes_paths():
    m = Metrics()
    m.inc("x", {"a": "1"})
    m.inc("x", {"a": "1"})
    assert m.counter_value("x", {"a": "1"}) == 2
    assert normalize_path("/analyze/verdicts/123456") == "/analyze/verdicts/{id}"
    assert normalize_path("/analyze/verdicts/3f2c6b1a-1111-2222-3333-444455556666") == "/analyze/verdicts/{id}"
    assert normalize_path("/analyze/url") == "/analyze/url"


def test_event_bus_drops_oldest_when_full_and_caps_subscribers():
    bus = EventBus(max_subscribers=1, queue_size=2)
    q = bus.subscribe()
    assert bus.subscribe() is None
    for i in range(5):
        bus.publish({"i": i})
    assert q.qsize() == 2


def test_list_matcher_deny_beats_allow_and_suffix_matches():
    m = ListMatcher([("allow", "example.com"), ("deny", "login.example.com")])
    assert m.check("https://login.example.com/x") == ("deny", "login.example.com")
    assert m.check("https://shop.example.com") == ("allow", "example.com")
    assert m.check("https://notexample.com") is None


def test_list_service_keeps_last_good_snapshot_on_loader_error():
    calls = {"n": 0}
    def loader():
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("db down")
        return [("deny", "evil.tk")]
    svc = ListService(loader, refresh_seconds=-1)   # always due for refresh
    svc.reload()
    assert svc.check("http://evil.tk") == ("deny", "evil.tk")
    assert svc.check("http://evil.tk") == ("deny", "evil.tk")  # 2nd call -> loader raises, snapshot kept


def test_normalize_domain_and_host_of():
    assert normalize_domain("HTTPS://*.Example.com:8080/path") == "example.com"
    assert normalize_domain("not a domain") is None
    assert host_of("http://Sub.Example.com/x") == "sub.example.com"


def test_csv_safe_neutralizes_formula_injection():
    assert csv_safe("=cmd|'/c calc'!A1").startswith("'")
    assert csv_safe("normal text") == "normal text"
    out = rows_to_csv(["a", "b"], [["=1+1", "x"]])
    assert "'=1+1" in out


def test_extract_urls_finds_and_limits():
    text = "visit http://a.com and https://b.com/x?y=1 and http://a.com again"
    urls = extract_urls(text, limit=5)
    assert urls.count("http://a.com") == 1  # deduped
    assert "https://b.com/x?y=1" in urls


def test_analyze_headers_flags_spf_fail_and_mismatch():
    raw = (
        "Authentication-Results: mx.example.com; spf=fail smtp.mailfrom=evil.tk; dkim=none; dmarc=fail\n"
        "From: PayPal Support <alerts@evil.tk>\n"
        "Return-Path: <bounce@other.tk>\n"
    )
    result = analyze_headers(raw)
    assert result is not None
    assert result["score"] > 0.5
    assert result["authentication"]["spf"] == "fail"


def test_analyze_html_flags_mismatched_link_and_password_form():
    html = '<a href="http://evil.tk">https://mybank.com/login</a><form><input type="password"></form>'
    result = analyze_html(html)
    assert result["score"] > 0
    assert any("mismatch" in r.lower() or "password" in r.lower() for r in result["reasons"])
