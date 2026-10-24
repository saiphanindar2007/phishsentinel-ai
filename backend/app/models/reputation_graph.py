"""
PhishSentinel AI — Sender Reputation Graph
----------------------------------------------
Tracks sender -> recipient relationships to catch anomalous behaviour:
brand-new senders and senders who suddenly contact many recipients at
once (a classic campaign signature).

Production notes:
  * Thread-safe — requests run in a threadpool, and NetworkX graphs are
    not safe to mutate concurrently.
  * Memory-bounded — edges older than `max_age` are pruned and the
    first-seen table is an LRU capped at `max_senders`, so a long-running
    process (or a flood of random sender addresses) can't grow it forever.
    A sender evicted from the table simply looks "new" again.
  * In-memory by design: state resets on restart. For persistent,
    multi-worker reputation, back this class with Redis/Postgres (same
    `analyze()` interface).
"""
import threading
from collections import OrderedDict
from datetime import datetime, timedelta

import networkx as nx


class ReputationGraph:
    def __init__(self, max_age: timedelta = timedelta(hours=24), max_senders: int = 50_000):
        self.graph = nx.DiGraph()
        self.first_seen: "OrderedDict[str, datetime]" = OrderedDict()
        self.max_age = max_age
        self.max_senders = max_senders
        self._lock = threading.Lock()
        self._ops = 0

    @staticmethod
    def _domain(email: str) -> str:
        return email.split("@")[-1].lower() if "@" in email else email.lower()

    def _record(self, sender: str, recipient: str, now: datetime) -> None:
        self.graph.add_edge(sender, recipient, ts=now)
        if sender in self.first_seen:
            self.first_seen.move_to_end(sender)
        else:
            self.first_seen[sender] = now
            while len(self.first_seen) > self.max_senders:
                evicted, _ = self.first_seen.popitem(last=False)
                if self.graph.has_node(evicted):
                    self.graph.remove_node(evicted)

    def _prune(self, now: datetime) -> None:
        cutoff = now - self.max_age
        stale = [(u, v) for u, v, d in self.graph.edges(data=True) if d["ts"] < cutoff]
        self.graph.remove_edges_from(stale)
        self.graph.remove_nodes_from([n for n in list(self.graph.nodes) if self.graph.degree(n) == 0])

    def record_email(self, sender: str, recipient: str = "unknown@local") -> None:
        with self._lock:
            self._record(sender, recipient, datetime.utcnow())

    def analyze(self, sender: str, recipient: str = "unknown@local") -> dict:
        now = datetime.utcnow()
        with self._lock:
            self._ops += 1
            if self._ops % 1000 == 0:
                self._prune(now)

            is_first_contact = sender not in self.first_seen
            recent_recipients = set()
            if self.graph.has_node(sender):
                for _, dst, data in self.graph.out_edges(sender, data=True):
                    if now - data["ts"] < timedelta(hours=1):
                        recent_recipients.add(dst)

            score = 0.0
            reasons = []
            if is_first_contact:
                score += 0.35
                reasons.append("First-ever contact from this sender")
            if len(recent_recipients) >= 20:
                score += 0.45
                reasons.append(f"Sender contacted {len(recent_recipients)} recipients in the last hour")
            elif len(recent_recipients) >= 5:
                score += 0.2
                reasons.append(f"Sender contacted {len(recent_recipients)} recipients recently")

            # Record AFTER scoring so this email doesn't inflate its own signal.
            self._record(sender, recipient, now)

        return {"score": max(0.0, min(1.0, score)), "method": "graph_heuristic", "reasons": reasons}

    def stats(self) -> dict:
        with self._lock:
            return {"senders_tracked": len(self.first_seen), "edges": self.graph.number_of_edges()}


reputation_graph = ReputationGraph()
