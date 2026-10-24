"""
PhishSentinel AI — Request middleware (pure ASGI)
-----------------------------------------------------
One layer that gives every request:
  * a request id (accepted from X-Request-ID if well-formed, else generated),
    echoed in the response and attached to every log line
  * a structured access log line with latency
  * Prometheus metrics (count by route/status, latency histogram)
  * standard security headers
  * an early 413 for oversized bodies (by Content-Length)

Written as raw ASGI instead of BaseHTTPMiddleware so it never buffers or
interferes with the Server-Sent-Events stream.

Note: chunked uploads without a Content-Length are bounded by the
per-field limits in schemas.py and, in the provided nginx config, by
`client_max_body_size`.
"""
import json
import logging
import re
import time
import uuid

from app.config import IS_PRODUCTION, MAX_REQUEST_BYTES
from app.logging_config import request_id_var
from app.services.metrics import metrics, normalize_path

logger = logging.getLogger("phishsentinel.access")

_RID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

_BASE_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
    (b"cross-origin-resource-policy", b"same-site"),
]
_API_ONLY_HEADERS = [
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]
if IS_PRODUCTION:
    _BASE_SECURITY_HEADERS.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        supplied = headers.get(b"x-request-id", b"").decode("latin-1")
        rid = supplied if _RID_OK.match(supplied) else uuid.uuid4().hex
        token = request_id_var.set(rid)

        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        started = time.perf_counter()
        state = {"status": 500}

        # Early reject of oversized bodies
        try:
            declared = int(headers.get(b"content-length", b"0") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_REQUEST_BYTES:
            state["status"] = 413
            body = json.dumps({"detail": f"Request body too large (limit {MAX_REQUEST_BYTES} bytes)"}).encode()
            await send({"type": "http.response.start", "status": 413, "headers": [
                (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                (b"x-request-id", rid.encode()), *_BASE_SECURITY_HEADERS]})
            await send({"type": "http.response.body", "body": body})
            self._finish(method, path, state["status"], started)
            request_id_var.reset(token)
            return

        is_docs = path.startswith(_DOC_PATHS)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                out = list(message.get("headers", []))
                present = {k.lower() for k, _ in out}
                out.append((b"x-request-id", rid.encode()))
                for k, v in _BASE_SECURITY_HEADERS:
                    if k not in present:
                        out.append((k, v))
                if not is_docs:
                    for k, v in _API_ONLY_HEADERS:
                        if k not in present:
                            out.append((k, v))
                    if b"cache-control" not in present:
                        out.append((b"cache-control", b"no-store"))
                message["headers"] = out
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("unhandled error", extra={"method": method, "path": path})
            raise
        finally:
            self._finish(method, path, state["status"], started)
            request_id_var.reset(token)

    @staticmethod
    def _finish(method: str, path: str, status: int, started: float) -> None:
        elapsed = time.perf_counter() - started
        route = normalize_path(path)
        metrics.inc("phishsentinel_http_requests_total", {"method": method, "route": route, "status": str(status)})
        metrics.observe("phishsentinel_http_request_duration_seconds", route, elapsed)
        level = logging.DEBUG if path in _QUIET_PATHS else logging.INFO
        logger.log(level, "request", extra={"method": method, "path": path, "status": status,
                                            "duration_ms": round(elapsed * 1000, 2)})
