from app.models.fusion_engine import fuse


def _signal(score, reasons=None):
    return {"score": score, "reasons": reasons or []}


def test_all_clean_signals_yield_safe_verdict():
    result = fuse(_signal(0.0), _signal(0.0), _signal(0.0), _signal(0.0))
    assert result["verdict"] == "safe"
    assert result["confidence"] == 0.0
    assert "verdict_id" in result


def test_high_signals_yield_phishing_verdict():
    result = fuse(
        _signal(0.9, ["Raw IP host"]),
        _signal(0.9, ["Credential harvesting language"]),
        _signal(0.9, ["Clone of a known brand page"]),
        _signal(0.9, ["First-ever contact, mass mailout"]),
    )
    assert result["verdict"] == "phishing"
    assert result["confidence"] >= 0.7
    assert len(result["top_reasons"]) > 0


def test_mid_range_signals_yield_suspicious_verdict():
    # Default weights: url=0.30, nlp=0.30, visual=0.20, reputation=0.20.
    # 0.8 on url+nlp alone = 0.8*0.30 + 0.8*0.30 = 0.48, safely inside the
    # suspicious band (0.4-0.7) without needing every signal to fire —
    # the original version of this test used 0.5, which only reaches
    # 0.30 combined confidence (below the 0.4 threshold) and was
    # asserting a verdict the fusion math could never produce.
    result = fuse(_signal(0.8), _signal(0.8), _signal(0.0), _signal(0.0))
    assert result["verdict"] == "suspicious", result


def test_confidence_is_weighted_average_not_max():
    # One maxed-out signal alone shouldn't push the whole score to 1.0 —
    # fusion must be a weighted blend, not "worst signal wins".
    result = fuse(_signal(1.0), _signal(0.0), _signal(0.0), _signal(0.0))
    assert 0.0 < result["confidence"] < 1.0


def test_custom_weights_are_respected():
    url_only = {"url": 1.0, "nlp": 0.0, "visual": 0.0, "reputation": 0.0}
    result = fuse(_signal(0.8), _signal(1.0), _signal(1.0), _signal(1.0), weights=url_only)
    assert result["confidence"] == 0.8


def test_top_reasons_prioritise_highest_weighted_contributor():
    result = fuse(
        _signal(0.9, ["url reason"]),
        _signal(0.1, ["nlp reason"]),
        _signal(0.0),
        _signal(0.0),
    )
    assert result["top_reasons"][0] == "url reason"


def test_no_reasons_falls_back_to_default_message():
    result = fuse(_signal(0.0), _signal(0.0), _signal(0.0), _signal(0.0))
    assert "No significant" in result["top_reasons"][0]
