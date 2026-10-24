"""
PhishSentinel AI — Authentication, authorisation & rate limiting
--------------------------------------------------------------------
Two separate keys:
  - API_KEY        -> /analyze/*, /feedback          (clients: extension, dashboard)
  - ADMIN_API_KEY  -> lists, audit log, purge, model reload, /metrics
                      (operators only; sent as X-Admin-Key)

Hardening over a naive implementation:
  * Constant-time key comparison (hmac.compare_digest) — no timing leaks.
  * Rate limits are keyed by CLIENT IP, never by the X-API-Key header.
    (Keying by the header would let an attacker send a different bogus key
    on every request to get a fresh bucket each time — bypassing the limit
    and growing memory without bound.)
  * Failed authentication attempts are throttled separately, so API keys
    can't be brute-forced at line speed.
  * Buckets are pruned, so memory stays bounded.
  * X-Forwarded-For is honoured only when TRUST_PROXY_HEADERS=true (and
    then the RIGHTMOST entry — the one our own proxy appended — is used,
    because the left side is client-controlled).
  * Dev convenience stays: with no keys configured and ENVIRONMENT !=
    production the API is open. app.config.validate_config() refuses to
    boot like that in production.

Single-process limiter (no Redis needed). Behind several workers each has
its own counters; swap `SlidingWindowLimiter` for a Redis-backed one (same
`check(key)` interface) if you scale out.
"""
import hashlib
import hmac
import threading
import time
from collections import deque
from typing import Deque, Dict

from fastapi import Header, HTTPException, Request, status

from app.config import (
    ADMIN_API_KEY,
    API_KEY,
    IS_PRODUCTION,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_PER_MINUTE,
    TRUST_PROXY_HEADERS,
)

AUTH_FAILURES_PER_MINUTE = 10


class SlidingWindowLimiter:
    def __init__(self, limit_per_window: int, window_seconds: int = 60, max_keys: int = 10000):
        self.limit = limit_per_window
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._ops = 0

    def _prune(self, now: float) -> None:
        stale = [k for k, d in self._hits.items() if not d or now - d[-1] > self.window]
        for k in stale:
            del self._hits[k]

    def check(self, key: str) -> bool:
        """Records a hit; returns False if the key is over its limit."""
        now = time.time()
        with self._lock:
            self._ops += 1
            if self._ops % 500 == 0 or len(self._hits) > self.max_keys:
                self._prune(now)
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def is_blocked(self, key: str) -> bool:
        """Read-only: would this key be refused right now?"""
        now = time.time()
        with self._lock:
            bucket = self._hits.get(key)
            if not bucket:
                return False
            recent = sum(1 for t in bucket if now - t <= self.window)
            return recent >= self.limit

    def size(self) -> int:
        with self._lock:
            return len(self._hits)


_limiter = SlidingWindowLimiter(RATE_LIMIT_PER_MINUTE)
_auth_failures = SlidingWindowLimiter(AUTH_FAILURES_PER_MINUTE)


def client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def actor_id(key: str) -> str:
    """Stable, non-reversible label for audit logs ('key:3f9a1c2b')."""
    if not key:
        return "anonymous"
    return "key:" + hashlib.sha256(key.encode()).hexdigest()[:8]


def _equal(supplied: str, expected: str) -> bool:
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def rate_limit(request: Request):
    """Dependency: 429 once a client IP exceeds RATE_LIMIT_PER_MINUTE."""
    if not RATE_LIMIT_ENABLED:
        return
    if not _limiter.check(f"ip:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} requests/minute). Please slow down.",
            headers={"Retry-After": "60"},
        )


def _reject(request: Request, detail: str, code: int = status.HTTP_401_UNAUTHORIZED):
    ip = client_ip(request)
    if not _auth_failures.check(f"authfail:{ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )
    raise HTTPException(status_code=code, detail=detail)


def _blocked_for_bruteforce(request: Request) -> None:
    if _auth_failures.is_blocked(f"authfail:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )


def require_api_key(request: Request, x_api_key: str = Header(default="")) -> str:
    """Dependency: enforces X-API-Key when API_KEY is configured. Returns
    an actor label for audit logging."""
    if not API_KEY:
        return "anonymous"
    _blocked_for_bruteforce(request)
    if not x_api_key or not _equal(x_api_key, API_KEY):
        _reject(request, "Missing or invalid X-API-Key header.")
    return actor_id(x_api_key)


def require_admin_key(
    request: Request,
    x_admin_key: str = Header(default=""),
    x_api_key: str = Header(default=""),
) -> str:
    """Dependency for operator-only endpoints.

    - ADMIN_API_KEY set  -> X-Admin-Key must match it.
    - not set, production -> endpoints are disabled outright (403).
    - not set, dev        -> falls back to the normal API-key rule so the
                             dashboard works locally with zero config.
    """
    if ADMIN_API_KEY:
        _blocked_for_bruteforce(request)
        if not x_admin_key or not _equal(x_admin_key, ADMIN_API_KEY):
            _reject(request, "Missing or invalid X-Admin-Key header.", status.HTTP_403_FORBIDDEN)
        return actor_id(x_admin_key)
    if IS_PRODUCTION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin endpoints are disabled: ADMIN_API_KEY is not set.")
    return require_api_key(request, x_api_key)
