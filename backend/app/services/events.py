"""
PhishSentinel AI — Live event bus (feeds the dashboard's Live Feed)
----------------------------------------------------------------------
Every verdict is published here; each connected dashboard holds a
subscription and receives events over Server-Sent Events.

Design points:
  - Bounded per-subscriber queues: a slow/stalled browser can never
    consume unbounded memory — its oldest events are dropped instead.
  - Hard cap on concurrent subscribers (MAX_SSE_SUBSCRIBERS) so the
    stream endpoint can't be used to exhaust threads/sockets.
  - Process-local. With multiple worker processes a subscriber only sees
    events handled by its own worker; run a single worker, or swap this
    class for Redis pub/sub (same publish/subscribe interface).
"""
import queue
import threading
from typing import Optional


class EventBus:
    def __init__(self, max_subscribers: int = 50, queue_size: int = 100):
        self.max_subscribers = max_subscribers
        self.queue_size = queue_size
        self._subs = set()
        self._lock = threading.Lock()
        self.published = 0
        self.dropped = 0

    def subscribe(self) -> Optional["queue.Queue"]:
        """Returns a queue, or None if the subscriber cap is reached."""
        with self._lock:
            if len(self._subs) >= self.max_subscribers:
                return None
            q: "queue.Queue" = queue.Queue(maxsize=self.queue_size)
            self._subs.add(q)
            return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._lock:
            self._subs.discard(q)

    def publish(self, event: dict) -> int:
        """Fan an event out to every subscriber. Never blocks. Returns the
        number of subscribers it was delivered to."""
        with self._lock:
            subs = list(self._subs)
        self.published += 1
        delivered = 0
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()          # drop oldest
                    self.dropped += 1
                    q.put_nowait(event)
                except (queue.Empty, queue.Full):
                    continue
            delivered += 1
        return delivered

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)
