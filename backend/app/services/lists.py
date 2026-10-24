"""
PhishSentinel AI — Organisation allow/deny lists
----------------------------------------------------
Every real deployment needs overrides: "never flag our own intranet"
(allowlist) and "always block this campaign domain" (denylist) without
retraining anything.

Rules:
  - Entries are domains. `example.com` matches example.com AND any
    subdomain (login.example.com), never `notexample.com`.
  - DENY beats ALLOW if a host matches both.
  - A denylist hit yields confidence 1.0 / phishing; an allowlist hit
    yields 0.0 / safe. Both are recorded in the verdict's reasons so the
    override is visible and auditable, never silent.

`ListMatcher` is pure and fast (a set lookup per host-suffix). `ListService`
holds an immutable snapshot that's swapped atomically on reload, so
request threads never see a half-updated list.
"""
import ipaddress
import re
import threading
import time
from typing import Callable, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


def normalize_domain(value: str) -> Optional[str]:
    """Accepts 'HTTPS://*.Example.com:8080/path' -> 'example.com'. Returns
    None if the input isn't a valid domain or IP."""
    v = (value or "").strip().lower()
    if not v or len(v) > 300:
        return None
    if "://" in v:
        v = urlparse(v).hostname or ""
    else:
        v = v.split("/")[0].split("?")[0].split("#")[0]
        if v.startswith("[") or v.count(":") == 1:
            v = v.rsplit(":", 1)[0] if v.count(":") == 1 else v
    v = v.removeprefix("*.").strip(".")
    if not v:
        return None
    try:
        ipaddress.ip_address(v)
        return v
    except ValueError:
        pass
    return v if _DOMAIN_RE.match(v) else None


def host_of(url: str) -> str:
    try:
        return (urlparse(url if "://" in url else "http://" + url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _suffixes(host: str) -> Iterable[str]:
    """'a.b.example.com' -> a.b.example.com, b.example.com, example.com, com"""
    labels = host.split(".")
    for i in range(len(labels)):
        yield ".".join(labels[i:])


class ListMatcher:
    def __init__(self, entries: Iterable[Tuple[str, str]] = ()):
        self.allow = set()
        self.deny = set()
        for kind, domain in entries:
            d = normalize_domain(domain)
            if not d:
                continue
            (self.deny if kind == "deny" else self.allow).add(d)

    def check(self, url: str) -> Optional[Tuple[str, str]]:
        """Returns ('deny'|'allow', matched_domain) or None."""
        host = host_of(url)
        if not host:
            return None
        for suffix in _suffixes(host):
            if suffix in self.deny:
                return ("deny", suffix)
        for suffix in _suffixes(host):
            if suffix in self.allow:
                return ("allow", suffix)
        return None

    def counts(self) -> dict:
        return {"allow": len(self.allow), "deny": len(self.deny)}


class ListService:
    """Holds the live matcher and refreshes it from storage periodically,
    so edits made through one worker/process show up in the others within
    `refresh_seconds` even without a shared cache."""

    def __init__(self, loader: Callable[[], List[Tuple[str, str]]], refresh_seconds: int = 30,
                 clock: Callable[[], float] = time.monotonic):
        self._loader = loader
        self._refresh = refresh_seconds
        self._clock = clock
        self._matcher = ListMatcher()
        self._loaded_at = -1e18
        self._lock = threading.Lock()

    def reload(self) -> None:
        entries = self._loader()
        matcher = ListMatcher(entries)           # build fully, then swap
        with self._lock:
            self._matcher = matcher
            self._loaded_at = self._clock()

    def check(self, url: str) -> Optional[Tuple[str, str]]:
        if self._clock() - self._loaded_at > self._refresh:
            try:
                self.reload()
            except Exception:
                # Storage hiccup: keep serving the last good snapshot
                self._loaded_at = self._clock()
        return self._matcher.check(url)

    def counts(self) -> dict:
        return self._matcher.counts()
