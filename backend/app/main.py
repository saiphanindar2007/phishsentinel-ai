"""
PhishSentinel AI — Application entry point
------------------------------------------------
    uvicorn app.main:app --port 8000          (dev: add --reload)

Startup order matters: logging -> config validation (fail closed in
production) -> database -> org lists -> optional retention purge.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware

configure_logging(config.LOG_LEVEL, config.LOG_JSON)
logger = logging.getLogger("phishsentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    errors, warnings = config.validate_config()
    for w in warnings:
        logger.warning("config: %s", w)
    for e in errors:
        logger.error("config: %s", e)
    if errors and config.IS_PRODUCTION:
        raise RuntimeError("Refusing to start with unsafe configuration: " + "; ".join(errors))

    from app.db import crud
    from app.db.database import SessionLocal, init_db
    from app.services.runtime import list_service

    init_db()
    try:
        list_service.reload()
    except Exception:
        logger.exception("could not load org lists at startup")
    if config.RETENTION_DAYS > 0:
        db = SessionLocal()
        try:
            logger.info("retention purge: %s", crud.purge_older_than(db, config.RETENTION_DAYS))
        finally:
            db.close()
    logger.info("PhishSentinel AI %s started (env=%s)", config.APP_VERSION, config.ENVIRONMENT)
    yield


app = FastAPI(
    title="PhishSentinel AI",
    description="Multi-signal, explainable phishing detection API.",
    version=config.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if config.DOCS_ENABLED else None,
    redoc_url="/redoc" if config.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if config.DOCS_ENABLED else None,
)

# Middleware order: added last = outermost. Request context wraps CORS so
# even CORS preflights get request ids, security headers and metrics.
_wildcard = "*" in config.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=not _wildcard,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Admin-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
)
app.add_middleware(RequestContextMiddleware)

from app.routers import admin, analyze, events, evaluation, feedback, lists, system  # noqa: E402

for r in (analyze.router, feedback.router, lists.router, events.router, admin.router, system.router, evaluation.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def root():
    return {"service": "PhishSentinel AI", "version": config.APP_VERSION,
            "docs": "/docs" if config.DOCS_ENABLED else None, "health": "/health/ready"}
