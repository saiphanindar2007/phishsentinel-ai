"""
PhishSentinel AI — Backend Configuration
-----------------------------------------
All environment-driven settings live here. Copy `.env.example` to `.env`
and adjust values before running the server.

`validate_config()` is called at startup. In ENVIRONMENT=production it
refuses to boot with unsafe settings (no API key, wildcard CORS, ...)
instead of silently running wide open.
"""
import os
from pathlib import Path
from typing import List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = "2.0.0"


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


# --- Environment --------------------------------------------------------
# "development" (default) | "test" | "production"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# --- Database -----------------------------------------------------------
# SQLite by default (zero setup). For production use Postgres, e.g.
# postgresql+psycopg://user:pass@host:5432/phishsentinel
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/phishsentinel.db")

# --- Model artifact paths ------------------------------------------------
# If a trained model exists at these paths it is loaded automatically;
# otherwise the system falls back to transparent heuristic scoring.
URL_MODEL_PATH = os.getenv("URL_MODEL_PATH", str(BASE_DIR / "training" / "artifacts" / "url_model.pkl"))
NLP_MODEL_DIR = os.getenv("NLP_MODEL_DIR", str(BASE_DIR / "training" / "artifacts" / "nlp_model"))

# --- Fusion weights (must sum to 1.0) ------------------------------------
FUSION_WEIGHTS = {
    "url": float(os.getenv("WEIGHT_URL", "0.30")),
    "nlp": float(os.getenv("WEIGHT_NLP", "0.30")),
    "visual": float(os.getenv("WEIGHT_VISUAL", "0.20")),
    "reputation": float(os.getenv("WEIGHT_REPUTATION", "0.20")),
}

# --- Verdict thresholds ---------------------------------------------------
SUSPICIOUS_THRESHOLD = float(os.getenv("SUSPICIOUS_THRESHOLD", "0.4"))
PHISHING_THRESHOLD = float(os.getenv("PHISHING_THRESHOLD", "0.7"))

# --- CORS -------------------------------------------------------------------
CORS_ORIGINS: List[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# --- Auth -------------------------------------------------------------------
# API_KEY guards /analyze and /feedback. ADMIN_API_KEY guards everything
# that changes state or exposes operations data (lists, audit, purge,
# model reload, metrics). Empty = open (development only).
API_KEY = os.getenv("API_KEY", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# --- Rate limiting ------------------------------------------------------------
RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", "true")
RATE_LIMIT_PER_MINUTE = _int("RATE_LIMIT_PER_MINUTE", "60")
# Only trust X-Forwarded-For when running behind a proxy you control
# (nginx, a load balancer). Otherwise clients could spoof their IP and
# dodge the limiter.
TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", "false")

# --- Explainability ---------------------------------------------------------
SHAP_ENABLED = _bool("SHAP_ENABLED", "true")

# --- Performance ----------------------------------------------------------------
CACHE_TTL_SECONDS = _int("CACHE_TTL_SECONDS", "300")
CACHE_MAX_ENTRIES = _int("CACHE_MAX_ENTRIES", "5000")
MAX_BATCH_SIZE = _int("MAX_BATCH_SIZE", "100")
MAX_REQUEST_BYTES = _int("MAX_REQUEST_BYTES", str(8 * 1024 * 1024))
MAX_SSE_SUBSCRIBERS = _int("MAX_SSE_SUBSCRIBERS", "50")
LIST_REFRESH_SECONDS = _int("LIST_REFRESH_SECONDS", "30")

# --- Observability --------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON = _bool("LOG_JSON", "true" if IS_PRODUCTION else "false")
DOCS_ENABLED = _bool("DOCS_ENABLED", "false" if IS_PRODUCTION else "true")

# --- Data retention ----------------------------------------------------------------
# Verdicts/feedback older than this are deleted at startup and by
# POST /admin/purge. 0 disables automatic purging.
RETENTION_DAYS = _int("RETENTION_DAYS", "0")


def validate_config() -> Tuple[List[str], List[str]]:
    """Returns (errors, warnings). Errors are fatal in production (the app
    refuses to start, see app.main); in other environments they are only
    logged. Warnings are always just logged."""
    errors: List[str] = []
    warnings: List[str] = []

    total = sum(FUSION_WEIGHTS.values())
    if abs(total - 1.0) > 1e-6:
        errors.append(f"Fusion weights sum to {total:.3f}, expected 1.0")
    if not (0.0 <= SUSPICIOUS_THRESHOLD < PHISHING_THRESHOLD <= 1.0):
        errors.append("Thresholds must satisfy 0 <= SUSPICIOUS_THRESHOLD < PHISHING_THRESHOLD <= 1")

    if IS_PRODUCTION:
        if not API_KEY:
            errors.append("API_KEY is empty - refusing to run an open API in production")
        if not ADMIN_API_KEY:
            errors.append("ADMIN_API_KEY is empty - admin endpoints would be unprotected")
        if API_KEY and ADMIN_API_KEY and API_KEY == ADMIN_API_KEY:
            errors.append("API_KEY and ADMIN_API_KEY must differ")
        if "*" in CORS_ORIGINS:
            errors.append("CORS_ORIGINS must list explicit origins in production (not '*')")
        if DATABASE_URL.startswith("sqlite"):
            warnings.append("SQLite is single-writer; use Postgres (DATABASE_URL) for real traffic")
    else:
        if not API_KEY:
            warnings.append("API_KEY is empty - API is open (fine for local development only)")
    return errors, warnings
