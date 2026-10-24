"""
PhishSentinel AI — Feedback Router
----------------------------------------
The dashboard and the browser extension send analyst corrections here.
Corrected verdicts are exported for retraining (training/
export_feedback_for_retraining.py), closing the learning loop.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import get_db
from app.schemas import FeedbackRequest, FeedbackResponse, FlagForReviewRequest, ReviewResolveRequest
from app.security import rate_limit, require_admin_key, require_api_key

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)


@router.post("", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    if crud.get_verdict(db, req.verdict_id) is None:
        raise HTTPException(status_code=404, detail="Unknown verdict_id")
    if not req.is_correct and not req.actual_label:
        raise HTTPException(status_code=422, detail="actual_label is required when is_correct is false")
    crud.save_feedback(db, req.verdict_id, req.is_correct, req.actual_label, req.source)
    return FeedbackResponse(status="ok", message="Feedback recorded. It will be included in the next retraining run.")


@router.get("/summary")
def feedback_summary(db: Session = Depends(get_db)):
    return crud.feedback_summary(db)


# --------------------------------------------------------------- review queue
# A lighter-weight workflow than /feedback: an analyst (or, later, an
# automatic "low confidence" rule) can flag a verdict for a second look
# without yet knowing the correct label. An admin then resolves it as
# "upheld" (model was right) or "overturned" (and records the correct
# label, which doubles as feedback for retraining).

@router.post("/flag", response_model=dict)
def flag_for_review(req: FlagForReviewRequest, db: Session = Depends(get_db)):
    if crud.get_verdict(db, req.verdict_id) is None:
        raise HTTPException(status_code=404, detail="Unknown verdict_id")
    record = crud.flag_for_review(db, req.verdict_id, req.note, req.source)
    return crud.review_to_dict(record)


@router.get("/queue")
def get_review_queue(
    status: Optional[str] = Query(None, pattern="^(pending|upheld|overturned)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = crud.list_review_queue(db, status, limit, offset)
    items = [crud.review_to_dict(r, crud.get_verdict(db, r.verdict_id)) for r in rows]
    return {"total": total, "items": items}


@router.get("/queue/summary")
def get_review_queue_summary(db: Session = Depends(get_db)):
    return crud.review_queue_summary(db)


@router.post("/queue/{review_id}/resolve", dependencies=[Depends(require_admin_key)])
def resolve_review_item(review_id: str, req: ReviewResolveRequest, db: Session = Depends(get_db)):
    if req.outcome == "overturned" and not req.actual_label:
        raise HTTPException(status_code=422, detail="actual_label is required when outcome is 'overturned'")
    record = crud.resolve_review(db, review_id, req.outcome, req.actual_label, req.note)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown review_id")
    # Overturning a verdict is itself analyst feedback — feed it into the
    # same retraining pipeline as /feedback.
    if req.outcome == "overturned":
        crud.save_feedback(db, record.verdict_id, is_correct=False, actual_label=req.actual_label, source="web")
    return crud.review_to_dict(record)
