from app.models.url_analyzer import extract_features, heuristic_score, url_analyzer


def test_legit_domain_scores_low():
    result = url_analyzer.analyze("https://www.google.com/search?q=hello")
    assert result["score"] < 0.3


def test_ip_host_is_flagged():
    f = extract_features("http://192.168.1.5/login")
    assert f.has_ip_host is True
    assert heuristic_score(f) > 0.2


def test_typosquat_of_known_brand_is_flagged():
    result = url_analyzer.analyze("http://paypa1-secure-login.com/verify")
    assert result["score"] > 0.3
    assert any("typosquat" in r.lower() or "resembles" in r.lower() for r in result["reasons"])


def test_url_shortener_increases_score_relative_to_baseline():
    plain = url_analyzer.analyze("https://example.com/page")
    shortened = url_analyzer.analyze("https://bit.ly/3xyzabc")
    assert shortened["score"] >= plain["score"]


def test_no_https_is_flagged_in_reasons():
    result = url_analyzer.analyze("http://example-shop.com/checkout")
    assert any("https" in r.lower() for r in result["reasons"])


def test_suspicious_tld_increases_score():
    f = extract_features("http://free-prize-claim.tk")
    assert f.suspicious_tld is True
    assert heuristic_score(f) > 0.1


def test_credential_keywords_are_counted():
    f = extract_features("http://example.com/login/verify/account/confirm")
    assert f.suspicious_keyword_hits >= 3
