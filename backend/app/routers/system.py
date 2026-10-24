"""
PhishSentinel AI — Health, readiness, metrics and system info
-----------------------------------------------------------------
  /health, /health/live   liveness (process is up) — never touches the DB
  /health/ready           readiness (DB reachable) — 503 when not
  /metrics                Prometheus text format (admin key)
  /system/info            versions, model state, cache/list/limiter stats (admin key)
"""
import platform
import time

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import APP_VERSION, ENVIRONMENT, RETENTION_DAYS
from app.db.database import check_db
from app.models.reputation_graph import reputation_graph
from app.models.url_analyzer import url_analyzer
from app.security import _limiter, require_admin_key
from app.services.metrics import metrics
from app.services.runtime import event_bus, list_service, url_cache

router = APIRouter(tags=["system"])
_STARTED = time.time()


@router.get("/health")
@router.get("/health/live")
def live():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/health/ready")
def ready():
    db_ok = check_db()
    body = {"status": "ready" if db_ok else "degraded", "database": db_ok}
    return JSONResponse(body, status_code=200 if db_ok else 503)


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus(actor: str = Depends(require_admin_key)):
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


@router.get("/system/info")
def info(actor: str = Depends(require_admin_key)):
    return {
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "python": platform.python_version(),
        "uptime_seconds": int(time.time() - _STARTED),
        "database": check_db(),
        "url_model_loaded": url_analyzer.model is not None,
        "cache": url_cache.stats(),
        "lists": list_service.counts(),
        "live_subscribers": event_bus.subscriber_count,
        "rate_limiter_keys": _limiter.size(),
        "reputation_graph": reputation_graph.stats(),
        "retention_days": RETENTION_DAYS,
        "metrics": metrics.snapshot(),
    }
