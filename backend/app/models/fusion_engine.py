"""
PhishSentinel AI — Fusion & Explainability Engine
------------------------------------------------------
This is the module that delivers the project's core USP: instead of one
brittle signal, four independent detectors are combined into a single
confidence score, AND every verdict comes with a plain-language reason.

Beyond the base fuse(), this module now also produces:
  * evidence_graph    — nodes/edges linking verdict -> signals -> individual
                         reasons, for the "Attack Evidence Graph" view.
  * counterfactual     — "what minimal change would flip this verdict",
                         computed analytically from the known weights.
  * confidence_detail  — a {level, score, unknown_evidence} block that is
                         honest about which detectors had no real input
                         (skipped/errored) instead of silently treating a
                         missing signal as "safe".

Note on explainability: a full SHAP integration is a natural upgrade once
you have a trained scikit-learn/XGBoost ensemble (see training/README.md
for how to wire SHAP's TreeExplainer/KernelExplainer in). For a rule +
weighted-sum fusion like this one, the weighted contribution of each
signal IS the explanation — which is what `top_reasons` reports below.
"""
from typing import Dict, List
import uuid

from app.config import FUSION_WEIGHTS, SUSPICIOUS_THRESHOLD, PHISHING_THRESHOLD

SIGNAL_LABELS = {
    "url": "URL & Domain Analysis",
    "nlp": "Content / NLP Analysis",
    "visual": "Visual Brand Check",
    "reputation": "Sender Reputation",
}

# Methods a detector reports when it had nothing real to work with — these
# must NOT be read as "this signal found nothing suspicious".
UNKNOWN_METHODS = {"skipped", "error", "no_reference_set", "no_data", ""}


def _unknown_evidence(signal_methods: Dict[str, str], weights: dict) -> List[dict]:
    """Which signals the verdict actually depends on (weight > 0) had no
    real evidence to score — a signal deliberately given 0 weight (e.g.
    single-URL scoring, where only 'url' is in play) is not 'unknown',
    it's simply not part of this verdict."""
    reason_text = {
        "skipped": "no screenshot was supplied",
        "no_reference_set": "no reference brand logos are configured",
        "error": "the detector raised an error",
        "no_data": "no input was available for this signal",
        "": "no input was available for this signal",
    }
    out = []
    for key, method in signal_methods.items():
        if weights.get(key, 0.0) <= 0:
            continue
        if method in UNKNOWN_METHODS:
            out.append({
                "signal": key,
                "label": SIGNAL_LABELS.get(key, key),
                "reason": reason_text.get(method, "no input was available for this signal"),
            })
    return out


def _confidence_block(fused_score: float, verdict: str, unknown: List[dict]) -> dict:
    """A verdict near a threshold, or resting on fewer live signals, is
    less certain than the raw number alone implies — surface that."""
    margin = min(abs(fused_score - SUSPICIOUS_THRESHOLD), abs(fused_score - PHISHING_THRESHOLD))
    if len(unknown) >= 2 or margin < 0.05:
        level = "low"
    elif len(unknown) == 1 or margin < 0.15:
        level = "medium"
    else:
        level = "high"
    notes = []
    if unknown:
        missing = ", ".join(u["label"] for u in unknown)
        notes.append(f"{len(unknown)} of 4 signals had no usable evidence ({missing}); the verdict rests on the rest.")
    if margin < 0.05:
        notes.append(f"Score {fused_score:.2f} sits within 0.05 of a threshold — a borderline call.")
    return {
        "level": level,
        "score": fused_score,
        "margin_to_nearest_threshold": round(margin, 3),
        "unknown_evidence": unknown,
        "note": " ".join(notes) or "All four signals produced usable evidence.",
    }


def _counterfactual(breakdown: dict, weights: dict, fused_score: float, verdict: str) -> dict:
    """Analytic 'what minimal change would flip this' explainer: for a
    weighted-sum fusion, flipping a verdict needs exactly
    delta = gap / weight[signal] of extra/less score on one signal — no
    search required, this is exact for the current fusion model."""
    key_map = {"url": "url_score", "nlp": "nlp_score", "visual": "visual_score", "reputation": "reputation_score"}

    if verdict == "safe":
        target, target_name, direction = SUSPICIOUS_THRESHOLD, "suspicious", "increase"
    elif verdict == "suspicious":
        target, target_name, direction = PHISHING_THRESHOLD, "phishing", "increase"
    else:
        target, target_name, direction = PHISHING_THRESHOLD, "suspicious", "decrease"

    gap = (target - fused_score) if direction == "increase" else (fused_score - target)
    scenarios = []
    for sig, w in weights.items():
        if w <= 0:
            continue
        current = breakdown.get(key_map[sig], 0.0)
        delta_needed = abs(gap) / w
        if direction == "increase":
            new_val = round(min(1.0, current + delta_needed), 3)
            feasible = new_val > current
            phrase = f"If {SIGNAL_LABELS[sig]} rose from {current:.2f} to {new_val:.2f}, the verdict would reach '{target_name}'."
        else:
            new_val = round(max(0.0, current - delta_needed), 3)
            feasible = new_val < current
            phrase = f"If {SIGNAL_LABELS[sig]} fell from {current:.2f} to {new_val:.2f}, the verdict would drop to '{target_name}'."
        scenarios.append({
            "signal": sig, "label": SIGNAL_LABELS[sig], "current_score": round(current, 3),
            "required_score": new_val, "delta": round(delta_needed, 3), "feasible": feasible,
            "explanation": phrase,
        })
    scenarios.sort(key=lambda s: s["delta"])  # smallest, most realistic flip first
    return {
        "current_verdict": verdict,
        "nearest_alternative_verdict": target_name,
        "direction": direction,
        "scenarios": scenarios[:4],
    }


def _evidence_graph(verdict_id: str, verdict: str, breakdown: dict, weights: dict, signal_reasons: Dict[str, List[str]]) -> dict:
    """Nodes/edges for a graph UI: a verdict node, one node per signal
    (sized by weighted contribution), and a leaf node per reason string."""
    key_map = {"url": "url_score", "nlp": "nlp_score", "visual": "visual_score", "reputation": "reputation_score"}
    nodes = [{"id": "verdict", "type": "verdict", "label": verdict.upper()}]
    edges = []
    for sig, label in SIGNAL_LABELS.items():
        score = breakdown.get(key_map[sig], 0.0)
        weight = weights.get(sig, 0.0)
        contribution = round(score * weight, 3)
        sig_id = f"signal:{sig}"
        nodes.append({
            "id": sig_id, "type": "signal", "label": label,
            "score": round(score, 3), "weight": weight, "contribution": contribution,
        })
        edges.append({"from": sig_id, "to": "verdict", "weight": contribution})
        for i, reason in enumerate(signal_reasons.get(sig, [])[:5]):
            reason_id = f"reason:{sig}:{i}"
            nodes.append({"id": reason_id, "type": "evidence", "label": reason})
            edges.append({"from": reason_id, "to": sig_id, "weight": 1.0})
    return {"verdict_id": verdict_id, "nodes": nodes, "edges": edges}


def fuse(url_result: dict, nlp_result: dict, visual_result: dict, reputation_result: dict, weights: dict = None) -> dict:
    weights = weights or FUSION_WEIGHTS
    breakdown = {
        "url_score": round(url_result["score"], 3),
        "nlp_score": round(nlp_result["score"], 3),
        "visual_score": round(visual_result["score"], 3),
        "reputation_score": round(reputation_result["score"], 3),
    }

    fused_score = (
        breakdown["url_score"] * weights["url"]
        + breakdown["nlp_score"] * weights["nlp"]
        + breakdown["visual_score"] * weights["visual"]
        + breakdown["reputation_score"] * weights["reputation"]
    )
    fused_score = round(max(0.0, min(1.0, fused_score)), 3)

    if fused_score >= PHISHING_THRESHOLD:
        verdict = "phishing"
    elif fused_score >= SUSPICIOUS_THRESHOLD:
        verdict = "suspicious"
    else:
        verdict = "safe"

    signal_reasons = {
        "url": url_result.get("reasons", []),
        "nlp": nlp_result.get("reasons", []),
        "visual": visual_result.get("reasons", []),
        "reputation": reputation_result.get("reasons", []),
    }
    # Rank each signal's WEIGHTED contribution to explain the verdict —
    # this is the "explainability" surfaced to the user in the dashboard
    # and the browser extension.
    contributions = [
        ("url", breakdown["url_score"] * weights["url"], signal_reasons["url"]),
        ("nlp", breakdown["nlp_score"] * weights["nlp"], signal_reasons["nlp"]),
        ("visual", breakdown["visual_score"] * weights["visual"], signal_reasons["visual"]),
        ("reputation", breakdown["reputation_score"] * weights["reputation"], signal_reasons["reputation"]),
    ]
    contributions.sort(key=lambda c: c[1], reverse=True)

    top_reasons: List[str] = []
    for _, weighted_score, reasons in contributions:
        if weighted_score > 0.02 and reasons:
            top_reasons.extend(reasons[:2])
        if len(top_reasons) >= 4:
            break

    if not top_reasons:
        top_reasons = ["No significant risk signals detected across URL, content, visual, or sender checks"]

    if verdict == "phishing":
        headline = "High-confidence phishing indicators detected."
    elif verdict == "suspicious":
        headline = "Some risk signals detected — proceed with caution."
    else:
        headline = "No significant phishing indicators found."

    explanation = headline + " Top factors: " + "; ".join(top_reasons[:3]) + "."

    verdict_id = str(uuid.uuid4())
    signal_methods = {
        "url": url_result.get("method", ""),
        "nlp": nlp_result.get("method", ""),
        "visual": visual_result.get("method", ""),
        "reputation": reputation_result.get("method", ""),
    }
    unknown = _unknown_evidence(signal_methods, weights)

    return {
        "verdict_id": verdict_id,
        "verdict": verdict,
        "confidence": fused_score,
        "breakdown": breakdown,
        "top_reasons": top_reasons[:4],
        "explanation": explanation,
        "confidence_detail": _confidence_block(fused_score, verdict, unknown),
        "counterfactual": _counterfactual(breakdown, weights, fused_score, verdict),
        "evidence_graph": _evidence_graph(verdict_id, verdict, breakdown, weights, signal_reasons),
    }
