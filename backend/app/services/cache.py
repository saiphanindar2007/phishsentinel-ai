"""
PhishSentinel AI — TTL + LRU cache
-------------------------------------
Browsers re-check the same URLs constantly (every navigation, every
tab restore), and email campaigns reuse the same link thousands of
times. Caching the URL analysis result keeps p95 latency flat under
load and saves CPU.

Thread-safe, bounded (LRU eviction) and time-limited (TTL). Pure
standard library. Process-local: with several workers each keeps its own
copy, which is fine for a cache. The cache is cleared whenever the model
is reloaded, so a promoted model never serves stale scores.
"""
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class TTLCache:
    def __init__(self, ttl_seconds: float = 300, max_entries: int = 5000, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._data: "OrderedDict[str, tuple]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str) -> Optional[Any]:
        if self.ttl <= 0:
            self.misses += 1
            return None
        now = self._clock()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self.misses += 1
                return None
            expires_at, value = item
            if expires_at <= now:
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        if self.ttl <= 0 or self.max_entries <= 0:
            return
        with self._lock:
            self._data[key] = (self._clock() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)
                self.evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            size = len(self._data)
        total = self.hits + self.misses
        return {
            "size": size,
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }
