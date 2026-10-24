"""
PhishSentinel AI — Admin operations (operator key required)
---------------------------------------------------------------
  POST /admin/reload-models   hot-swap the URL model from disk (clears cache)
  GET  /admin/audit           who did what, when, from where
  POST /admin/purge           delete verdicts/feedback older than N days
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import RETENTION_DAYS
from app.db import crud
from app.db.database import get_db
from app.logging_config import request_id_var
from app.models.url_analyzer import url_analyzer
from app.security import client_ip, rate_limit, require_admin_key
from app.services.runtime import url_cache

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(rate_limit)])


@router.post("/reload-models")
def reload_models(request: Request, db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    had = url_analyzer.model is not None
    url_analyzer.reload()
    url_cache.clear()                      # old verdicts came from the old model
    loaded = url_analyzer.model is not None
    crud.add_audit(db, actor, "reload_models", f"before={had} after={loaded}", client_ip(request), request_id_var.get() or "")
    return {
        "status": "ok", "model_was_loaded_before": had, "model_loaded_now": loaded,
        "note": "URL model reloaded from disk." if loaded else "No trained model on disk — using heuristic scoring.",
    }


@router.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    return [{"id": a.id, "created_at": a.created_at.isoformat() if a.created_at else None, "actor": a.actor,
             "action": a.action, "detail": a.detail, "ip": a.ip, "request_id": a.request_id}
            for a in crud.list_audit(db, limit, offset)]


@router.post("/purge")
def purge(request: Request, days: int = Query(None, ge=1, le=3650),
          db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    d = days or RETENTION_DAYS or 90
    result = crud.purge_older_than(db, d)
    crud.add_audit(db, actor, "purge", f"days={d} {result}", client_ip(request), request_id_var.get() or "")
    return {"status": "ok", "days": d, **result}
