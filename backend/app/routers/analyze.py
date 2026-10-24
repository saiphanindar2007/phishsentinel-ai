"""
PhishSentinel AI — Analyze Router
--------------------------------------
Scoring endpoints (URL, batch, email) plus the read APIs behind the
dashboard: history (paginated/filterable), single verdict, stats,
timeline, top flagged domains and CSV export.

Production behaviour:
  * Org allow/deny lists override the model (visible in the verdict).
  * URL verdicts are cached briefly — the extension re-checks the same
    page constantly. Cache hits are still recorded as history rows.
  * Optional detectors (NLP, visual, ...) are wrapped: if one crashes the
    request still succeeds with that signal at 0 and the error is counted
    in metrics, instead of returning a 500 to the user.
  * Emails: every URL in the body/HTML is extracted and the worst one is
    scored; SPF/DKIM/DMARC headers and HTML tricks feed the sender and
    content signals.
"""
import copy
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import FUSION_WEIGHTS
from app.db import crud
from app.db.database import get_db
from app.models.email_headers import analyze_headers
from app.models.fusion_engine import fuse
from app.models.html_analysis import analyze_html
from app.models.nlp_classifier import nlp_classifier
from app.models.reputation_graph import reputation_graph
from app.models.url_analyzer import url_analyzer
from app.models.url_extract import extract_urls
from app.models.attack_storyline import build_storyline
from app.models.visual_detector import visual_detector
from app.schemas import (BatchAnalyzeRequest, BatchItem, BatchResponse, EmailAnalyzeRequest,
                         URLAnalyzeRequest, VerdictResponse)
from app.security import actor_id, client_ip, rate_limit, require_admin_key, require_api_key
from app.services.csvsafe import rows_to_csv
from app.services.metrics import metrics
from app.services.runtime import event_bus, list_service, url_cache

logger = logging.getLogger("phishsentinel.analyze")

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)

ZERO = {"score": 0.0, "reasons": []}
URL_ONLY_WEIGHTS = {"url": 1.0, "nlp": 0.0, "visual": 0.0, "reputation": 0.0}


# ------------------------------------------------------------ helpers
def safe_call(name: str, fn, *args):
    """Run an optional detector; on failure count it and return a zero signal."""
    try:
        return fn(*args)
    except Exception:
        logger.exception("detector %s failed", name)
        metrics.inc("phishsentinel_detector_errors_total", {"detector": name})
        return {"score": 0.0, "reasons": [], "method": "error"}


def noisy_or(*scores: float) -> float:
    """Combine independent risk signals: 1 - prod(1 - s). Two moderate
    signals reinforce each other instead of one just masking the other."""
    p = 1.0
    for s in scores:
        p *= 1.0 - max(0.0, min(1.0, s))
    return round(1.0 - p, 3)


def merge(a: dict, b: Optional[dict]) -> dict:
    if not b:
        return a
    return {"score": noisy_or(a["score"], b["score"]), "reasons": list(a.get("reasons", [])) + list(b.get("reasons", [])),
            "method": a.get("method", "") + "+" + b.get("method", "")}


def _override_verdict(kind: str, domain: str) -> dict:
    deny = kind == "deny"
    reason = (f"Domain '{domain}' is on your organisation's denylist" if deny
              else f"Domain '{domain}' is on your organisation's allowlist")
    score = 1.0 if deny else 0.0
    sig = {"score": score, "reasons": [reason]}
    fused = fuse(sig, ZERO, ZERO, ZERO, weights=URL_ONLY_WEIGHTS)
    fused["verdict"] = "phishing" if deny else "safe"
    fused["confidence"] = score
    fused["override"] = "denylist" if deny else "allowlist"
    fused["top_reasons"] = [reason]
    fused["explanation"] = ("Blocked by policy. " if deny else "Allowed by policy. ") + reason + "."
    return fused


def score_url(url: str) -> dict:
    """Score one URL (lists -> cache -> model). Returns a fresh fused dict
    with a unique verdict_id every call."""
    hit = list_service.check(url)
    if hit:
        metrics.inc("phishsentinel_list_hits_total", {"kind": hit[0]})
        return _override_verdict(hit[0], hit[1])

    cached = url_cache.get(url)
    if cached is not None:
        metrics.inc("phishsentinel_cache_events_total", {"result": "hit"})
        out = copy.deepcopy(cached)
        out["verdict_id"] = str(uuid.uuid4())
        return out
    metrics.inc("phishsentinel_cache_events_total", {"result": "miss"})

    url_result = url_analyzer.analyze(url)
    fused = fuse(url_result, ZERO, ZERO, ZERO, weights=URL_ONLY_WEIGHTS)
    url_cache.set(url, copy.deepcopy(fused))
    return fused


def _publish(input_type: str, raw: str, fused: dict) -> None:
    metrics.inc("phishsentinel_verdicts_total", {"verdict": fused["verdict"], "input_type": input_type})
    event_bus.publish({
        "verdict_id": fused["verdict_id"], "input_type": input_type, "raw_input": raw[:300],
        "verdict": fused["verdict"], "confidence": fused["confidence"],
        "explanation": fused["explanation"], "override": fused.get("override"),
    })


def _record_audit(db: Session, request: Request, actor: str, action: str, detail: str) -> None:
    try:
        from app.logging_config import request_id_var
        crud.add_audit(db, actor, action, detail, ip=client_ip(request), request_id=request_id_var.get() or "")
    except Exception:
        db.rollback()
        logger.exception("audit write failed")


# ------------------------------------------------------------ scoring
@router.post("/url", response_model=VerdictResponse)
def analyze_url(req: URLAnalyzeRequest, db: Session = Depends(get_db)):
    """Used by the Chrome extension on every navigation. Only the URL signal
    applies, so it carries 100% of the fusion weight."""
    fused = score_url(req.url)
    crud.save_verdict(db, "url", req.url, fused)
    _publish("url", req.url, fused)
    return fused


@router.post("/batch", response_model=BatchResponse)
def analyze_batch(req: BatchAnalyzeRequest, db: Session = Depends(get_db)):
    """Scan up to MAX_BATCH_SIZE URLs in one call (SOC triage, mailbox
    sweeps). Stored in a single transaction."""
    results: List[BatchItem] = []
    to_save = []
    summary = {"safe": 0, "suspicious": 0, "phishing": 0}
    for url in req.urls:
        fused = score_url(url)
        summary[fused["verdict"]] += 1
        to_save.append(("batch", url, fused))
        results.append(BatchItem(input=url, verdict_id=fused["verdict_id"], verdict=fused["verdict"],
                                 confidence=fused["confidence"], top_reasons=fused["top_reasons"],
                                 override=fused.get("override")))
    crud.save_verdicts_bulk(db, to_save)
    for _, url, fused in to_save:
        _publish("batch", url, fused)
    return BatchResponse(count=len(results), summary=summary, results=results)


@router.post("/email", response_model=VerdictResponse)
def analyze_email(req: EmailAnalyzeRequest, db: Session = Depends(get_db)):
    """Email-gateway endpoint. Runs every available signal; signals with no
    input (no screenshot, no headers) have their weight redistributed so a
    missing signal never dilutes the verdict toward 'safe'."""
    # 1) URLs: explicit + extracted from text + hrefs from HTML
    html = safe_call("html", analyze_html, req.html_body) if req.html_body else None
    urls: List[str] = []
    for u in ([req.url] if req.url else []) + extract_urls(f"{req.subject}\n{req.body}") + (html or {}).get("hrefs", []):
        if u and u not in urls:
            urls.append(u)
    urls = urls[:10]

    url_result = dict(ZERO)
    override = None
    worst_fused = None
    hops: List[tuple] = []
    for u in urls:
        f = score_url(u)
        hops.append((u, f))
        if worst_fused is None or f["confidence"] > worst_fused["confidence"]:
            worst_fused = f
        if f.get("override") == "denylist":
            override = "denylist"
    if worst_fused:
        url_result = {"score": worst_fused["breakdown"]["url_score"] if worst_fused.get("override") is None else worst_fused["confidence"],
                      "reasons": worst_fused["top_reasons"]}

    # 2) content, visual, sender
    nlp_result = safe_call("nlp", nlp_classifier.analyze, f"{req.subject}\n{req.body}")
    if html:
        nlp_result = merge(nlp_result, {"score": html["score"], "reasons": html["reasons"], "method": "html"})
    visual_result = safe_call("visual", visual_detector.analyze, req.screenshot_base64, req.claimed_brand)
    reputation_result = safe_call("reputation", reputation_graph.analyze, req.sender, req.recipient or "unknown@local")
    headers = safe_call("headers", analyze_headers, req.raw_headers) if req.raw_headers else None
    if headers and "authentication" in headers:
        reputation_result = merge(reputation_result, {"score": headers["score"], "reasons": headers["reasons"], "method": "headers"})

    weights = dict(FUSION_WEIGHTS)
    if not req.screenshot_base64:
        redistribute = weights.pop("visual")
        remaining = sum(weights.values())
        weights = {k: v + redistribute * (v / remaining) for k, v in weights.items()}
        weights["visual"] = 0.0

    fused = fuse(url_result, nlp_result, visual_result, reputation_result, weights=weights)
    # A confirmed authentication failure or a denylisted link is decisive on its own.
    if override == "denylist":
        fused.update(verdict="phishing", confidence=1.0, override="denylist")
        fused["top_reasons"] = (["A link in this email points to a denylisted domain"] + fused["top_reasons"])[:4]
        fused["explanation"] = "Blocked by policy. " + fused["top_reasons"][0] + "."
    if headers and headers.get("authentication"):
        fused["authentication"] = headers["authentication"]
    if urls:
        fused["analyzed_urls"] = urls
        fused["storyline"] = build_storyline(hops)

    snapshot = f"FROM:{req.sender} SUBJECT:{req.subject[:200]} URL:{(urls[0] if urls else '')}"
    crud.save_verdict(db, "email", snapshot, fused)
    _publish("email", snapshot, fused)
    return fused


# ------------------------------------------------------------ read APIs
@router.get("/verdicts")
def list_verdicts(
    response: Response,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    verdict: Optional[str] = Query(None, pattern="^(safe|suspicious|phishing)$"),
    input_type: Optional[str] = Query(None, pattern="^(url|email|batch)$"),
    q: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
):
    """Paginated, filterable history. Total match count is in X-Total-Count."""
    rows, total = crud.query_verdicts(db, limit, offset, verdict, input_type, q)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [crud.verdict_to_dict(r) for r in rows]


@router.get("/verdicts/{verdict_id}")
def get_verdict(verdict_id: str, db: Session = Depends(get_db)):
    rec = crud.get_verdict(db, verdict_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Verdict not found")
    return crud.verdict_to_dict(rec)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return crud.stats(db)


@router.get("/timeline")
def get_timeline(hours: int = Query(24, ge=1, le=720), db: Session = Depends(get_db)):
    return crud.timeline(db, hours)


@router.get("/top-domains")
def get_top_domains(limit: int = Query(10, ge=1, le=50), hours: int = Query(168, ge=1, le=720), db: Session = Depends(get_db)):
    return crud.top_flagged_domains(db, limit, hours)


@router.get("/export.csv", response_class=PlainTextResponse)
def export_csv(
    request: Request,
    verdict: Optional[str] = Query(None, pattern="^(safe|suspicious|phishing)$"),
    q: Optional[str] = Query(None, max_length=200),
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    actor: str = Depends(require_api_key),
):
    """CSV export of history (formula-injection safe). Audited."""
    rows: list = []
    offset = 0
    while len(rows) < limit:
        page, _ = crud.query_verdicts(db, min(500, limit - len(rows)), offset, verdict, None, q)
        if not page:
            break
        rows.extend(page)
        offset += len(page)
    header = ["created_at", "verdict_id", "input_type", "verdict", "confidence", "url_score", "nlp_score",
              "visual_score", "reputation_score", "raw_input", "explanation"]
    data = [[r.created_at.isoformat() if r.created_at else "", r.verdict_id, r.input_type, r.verdict, r.confidence,
             r.url_score, r.nlp_score, r.visual_score, r.reputation_score, r.raw_input, r.explanation] for r in rows]
    _record_audit(db, request, actor, "export_csv", f"rows={len(rows)} verdict={verdict} q={q}")
    return PlainTextResponse(rows_to_csv(header, data), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="phishsentinel-verdicts.csv"'})
