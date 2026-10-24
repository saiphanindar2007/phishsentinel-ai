"""
PhishSentinel AI — CRUD Operations
---------------------------------------
Thin data-access layer. All SQL lives here so routers stay declarative and
the retraining scripts read through the same single source of truth.
Everything uses the ORM / bound parameters — no string-built SQL.
"""
import json
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import AuditRecord, FeedbackRecord, ListEntry, ReviewQueueRecord, VerdictRecord
from app.services.lists import host_of

VERDICTS = ("safe", "suspicious", "phishing")
_EXTRA_KEYS = ("confidence_detail", "counterfactual", "evidence_graph", "storyline")


def _extra_json(fused: dict) -> Optional[str]:
    extra = {k: fused[k] for k in _EXTRA_KEYS if fused.get(k) is not None}
    return json.dumps(extra) if extra else None


# --------------------------------------------------------------- verdicts
def save_verdict(db: Session, input_type: str, raw_input: str, fused: dict) -> VerdictRecord:
    record = VerdictRecord(
        verdict_id=fused["verdict_id"],
        input_type=input_type,
        raw_input=raw_input[:2000],
        verdict=fused["verdict"],
        confidence=fused["confidence"],
        url_score=fused["breakdown"]["url_score"],
        nlp_score=fused["breakdown"]["nlp_score"],
        visual_score=fused["breakdown"]["visual_score"],
        reputation_score=fused["breakdown"]["reputation_score"],
        explanation=fused["explanation"],
        extra_json=_extra_json(fused),
    )
    db.add(record)
    db.commit()
    return record


def save_verdicts_bulk(db: Session, items: List[Tuple[str, str, dict]]) -> None:
    """One transaction for a whole batch scan (items = (type, raw, fused))."""
    for input_type, raw, fused in items:
        db.add(VerdictRecord(
            verdict_id=fused["verdict_id"], input_type=input_type, raw_input=raw[:2000],
            verdict=fused["verdict"], confidence=fused["confidence"],
            url_score=fused["breakdown"]["url_score"], nlp_score=fused["breakdown"]["nlp_score"],
            visual_score=fused["breakdown"]["visual_score"], reputation_score=fused["breakdown"]["reputation_score"],
            explanation=fused["explanation"], extra_json=_extra_json(fused),
        ))
    db.commit()


def get_verdict(db: Session, verdict_id: str) -> Optional[VerdictRecord]:
    return db.query(VerdictRecord).filter(VerdictRecord.verdict_id == verdict_id).first()


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def query_verdicts(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    verdict: Optional[str] = None,
    input_type: Optional[str] = None,
    q: Optional[str] = None,
) -> Tuple[List[VerdictRecord], int]:
    """Filtered, paginated listing. Returns (rows, total_matching)."""
    query = db.query(VerdictRecord)
    if verdict in VERDICTS:
        query = query.filter(VerdictRecord.verdict == verdict)
    if input_type:
        query = query.filter(VerdictRecord.input_type == input_type)
    if q:
        query = query.filter(VerdictRecord.raw_input.ilike(f"%{_escape_like(q)}%", escape="\\"))
    total = query.count()
    rows = query.order_by(desc(VerdictRecord.created_at)).offset(max(offset, 0)).limit(max(1, min(limit, 500))).all()
    return rows, total


def verdict_to_dict(r: VerdictRecord) -> dict:
    out = {
        "verdict_id": r.verdict_id,
        "input_type": r.input_type,
        "raw_input": r.raw_input,
        "verdict": r.verdict,
        "confidence": r.confidence,
        "explanation": r.explanation,
        "breakdown": {
            "url_score": r.url_score,
            "nlp_score": r.nlp_score,
            "visual_score": r.visual_score,
            "reputation_score": r.reputation_score,
        },
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
    if r.extra_json:
        try:
            out.update(json.loads(r.extra_json))
        except (TypeError, ValueError):
            pass
    return out


def stats(db: Session) -> Dict[str, int]:
    counts = dict(db.query(VerdictRecord.verdict, func.count()).group_by(VerdictRecord.verdict).all())
    out = {v: int(counts.get(v, 0)) for v in VERDICTS}
    out["total"] = sum(out.values())
    return out


def timeline(db: Session, hours: int = 24) -> List[dict]:
    """Verdict counts per hour for the last `hours` hours (zero-filled so
    charts have no gaps). Bucketed in Python to stay database-agnostic."""
    hours = max(1, min(hours, 24 * 30))
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(hours=hours - 1)
    rows = (
        db.query(VerdictRecord.created_at, VerdictRecord.verdict)
        .filter(VerdictRecord.created_at >= start)
        .limit(200_000)
        .all()
    )
    buckets = {start + timedelta(hours=i): Counter() for i in range(hours)}
    for created_at, verdict in rows:
        if created_at is None:
            continue
        key = created_at.replace(minute=0, second=0, microsecond=0)
        if key in buckets:
            buckets[key][verdict] += 1
    return [
        {"hour": k.isoformat() + "Z", **{v: int(c.get(v, 0)) for v in VERDICTS}, "total": sum(c.values())}
        for k, c in sorted(buckets.items())
    ]


def top_flagged_domains(db: Session, limit: int = 10, hours: int = 24 * 7) -> List[dict]:
    """Most frequently flagged hosts (suspicious + phishing) recently —
    an analyst's 'what's being used against us' view."""
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(VerdictRecord.raw_input, VerdictRecord.verdict)
        .filter(VerdictRecord.created_at >= since, VerdictRecord.verdict.in_(("suspicious", "phishing")),
                VerdictRecord.input_type.in_(("url", "batch")))
        .order_by(desc(VerdictRecord.created_at))
        .limit(5000)
        .all()
    )
    counter: Counter = Counter()
    worst: Dict[str, str] = {}
    for raw, verdict in rows:
        host = host_of(raw or "")
        if not host:
            continue
        counter[host] += 1
        if verdict == "phishing" or host not in worst:
            worst[host] = verdict
    return [{"domain": d, "count": n, "worst_verdict": worst[d]} for d, n in counter.most_common(limit)]


# --------------------------------------------------------------- feedback
def save_feedback(db: Session, verdict_id: str, is_correct: bool, actual_label: Optional[str], source: str) -> FeedbackRecord:
    record = FeedbackRecord(
        id=str(uuid.uuid4()),
        verdict_id=verdict_id,
        is_correct=is_correct,
        actual_label=actual_label,
        source=source,
    )
    db.add(record)
    db.commit()
    return record


def feedback_summary(db: Session) -> dict:
    rows = db.query(FeedbackRecord.is_correct, func.count()).group_by(FeedbackRecord.is_correct).all()
    counts = {bool(k): int(v) for k, v in rows}
    correct, incorrect = counts.get(True, 0), counts.get(False, 0)
    total = correct + incorrect
    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "agreement_rate": round(correct / total, 4) if total else None,
    }


def get_feedback_dataset(db: Session):
    """(raw_input, actual_label) pairs for corrected verdicts — the shape the
    training scripts expect for incremental retraining."""
    rows = (
        db.query(VerdictRecord, FeedbackRecord)
        .join(FeedbackRecord, VerdictRecord.verdict_id == FeedbackRecord.verdict_id)
        .filter(FeedbackRecord.is_correct == False)  # noqa: E712
        .all()
    )
    return [(v.raw_input, f.actual_label) for v, f in rows if f.actual_label]


# --------------------------------------------------------------- lists
def list_entries(db: Session) -> List[ListEntry]:
    return db.query(ListEntry).order_by(ListEntry.kind, ListEntry.domain).all()


def list_pairs(db: Session) -> List[Tuple[str, str]]:
    return [(e.kind, e.domain) for e in db.query(ListEntry.kind, ListEntry.domain).all()]


def add_list_entry(db: Session, kind: str, domain: str, note: Optional[str], created_by: str) -> Optional[ListEntry]:
    entry = ListEntry(kind=kind, domain=domain, note=(note or "")[:200] or None, created_by=created_by)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None            # duplicate (kind, domain)
    db.refresh(entry)
    return entry


def delete_list_entry(db: Session, entry_id: int) -> Optional[ListEntry]:
    entry = db.query(ListEntry).filter(ListEntry.id == entry_id).first()
    if entry is None:
        return None
    db.delete(entry)
    db.commit()
    return entry


# --------------------------------------------------------------- audit
def add_audit(db: Session, actor: str, action: str, detail: str, ip: str = "", request_id: str = "") -> None:
    db.add(AuditRecord(actor=actor, action=action, detail=detail[:1000], ip=ip, request_id=request_id))
    db.commit()


def list_audit(db: Session, limit: int = 100, offset: int = 0) -> List[AuditRecord]:
    return (
        db.query(AuditRecord).order_by(desc(AuditRecord.created_at), desc(AuditRecord.id))
        .offset(max(offset, 0)).limit(max(1, min(limit, 500))).all()
    )


# --------------------------------------------------------------- review queue
def flag_for_review(db: Session, verdict_id: str, note: Optional[str], source: str) -> ReviewQueueRecord:
    record = ReviewQueueRecord(
        id=str(uuid.uuid4()), verdict_id=verdict_id, status="pending",
        flagged_note=(note or "")[:500] or None, flagged_source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def review_to_dict(r: ReviewQueueRecord, verdict: Optional[VerdictRecord] = None) -> dict:
    return {
        "id": r.id,
        "verdict_id": r.verdict_id,
        "status": r.status,
        "flagged_note": r.flagged_note,
        "flagged_source": r.flagged_source,
        "resolved_note": r.resolved_note,
        "actual_label": r.actual_label,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "verdict": verdict_to_dict(verdict) if verdict else None,
    }


def list_review_queue(db: Session, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[List[ReviewQueueRecord], int]:
    query = db.query(ReviewQueueRecord)
    if status:
        query = query.filter(ReviewQueueRecord.status == status)
    total = query.count()
    rows = query.order_by(desc(ReviewQueueRecord.created_at)).offset(max(offset, 0)).limit(max(1, min(limit, 500))).all()
    return rows, total


def get_review(db: Session, review_id: str) -> Optional[ReviewQueueRecord]:
    return db.query(ReviewQueueRecord).filter(ReviewQueueRecord.id == review_id).first()


def resolve_review(db: Session, review_id: str, outcome: str, actual_label: Optional[str], note: Optional[str]) -> Optional[ReviewQueueRecord]:
    record = get_review(db, review_id)
    if record is None:
        return None
    record.status = outcome
    record.actual_label = actual_label
    record.resolved_note = (note or "")[:500] or None
    record.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def review_queue_summary(db: Session) -> dict:
    rows = db.query(ReviewQueueRecord.status, func.count()).group_by(ReviewQueueRecord.status).all()
    counts = {status: int(n) for status, n in rows}
    return {
        "pending": counts.get("pending", 0),
        "upheld": counts.get("upheld", 0),
        "overturned": counts.get("overturned", 0),
        "total": sum(counts.values()),
    }


# --------------------------------------------------------------- retention
def purge_older_than(db: Session, days: int) -> dict:
    """Deletes verdicts and feedback older than `days`. Returns counts."""
    cutoff = datetime.utcnow() - timedelta(days=max(days, 1))
    fb = db.query(FeedbackRecord).filter(FeedbackRecord.created_at < cutoff).delete(synchronize_session=False)
    vd = db.query(VerdictRecord).filter(VerdictRecord.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return {"verdicts_deleted": int(vd), "feedback_deleted": int(fb), "cutoff": cutoff.isoformat() + "Z"}
