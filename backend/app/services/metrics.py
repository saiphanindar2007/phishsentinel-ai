"""
PhishSentinel AI — Metrics (Prometheus text format)
-------------------------------------------------------
Dependency-free counters and latency histograms, rendered in the
Prometheus exposition format at GET /metrics. Point Prometheus/Grafana
(or any compatible scraper) at it for request rate, error rate, latency
percentiles and verdict mix.

Labels are kept low-cardinality on purpose (route templates, not raw
URLs) so the metric set can't be blown up by a client sending random
paths.
"""
import re
import threading
from collections import defaultdict
from typing import Dict, Tuple

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_ID_SEGMENT = re.compile(
    r"^(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d+)$"
)


def normalize_path(path: str) -> str:
    """Collapses ids in a path so metrics labels stay low-cardinality:
    /analyze/verdicts/3f2c...-... -> /analyze/verdicts/{id}"""
    parts = path.split("/")
    out = ["{id}" if _ID_SEGMENT.match(p) else p for p in parts]
    return "/".join(out)[:120] or "/"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        self._hist_counts: Dict[Tuple[str, str], list] = {}
        self._hist_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self._hist_total: Dict[Tuple[str, str], int] = defaultdict(int)
        self._help: Dict[str, str] = {}

    def describe(self, name: str, help_text: str) -> None:
        self._help[name] = help_text

    def inc(self, name: str, labels: Dict[str, str] = None, amount: float = 1.0) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._counters[key] += amount

    def observe(self, name: str, route: str, seconds: float) -> None:
        key = (name, route)
        with self._lock:
            counts = self._hist_counts.setdefault(key, [0] * len(LATENCY_BUCKETS))
            for i, bound in enumerate(LATENCY_BUCKETS):
                if seconds <= bound:
                    counts[i] += 1
            self._hist_sum[key] += seconds
            self._hist_total[key] += 1

    def counter_value(self, name: str, labels: Dict[str, str] = None) -> float:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            return self._counters.get(key, 0.0)

    def snapshot(self) -> dict:
        """Small JSON summary for the dashboard's System tab."""
        with self._lock:
            requests = sum(v for (n, _), v in self._counters.items() if n == "phishsentinel_http_requests_total")
            errors_5xx = sum(
                v for (n, labels), v in self._counters.items()
                if n == "phishsentinel_http_requests_total" and dict(labels).get("status", "").startswith("5")
            )
            verdicts = {
                dict(labels).get("verdict", "?"): v
                for (n, labels), v in self._counters.items() if n == "phishsentinel_verdicts_total"
            }
            total_lat = sum(self._hist_sum.values())
            total_cnt = sum(self._hist_total.values())
        return {
            "requests_total": int(requests),
            "errors_5xx": int(errors_5xx),
            "avg_latency_ms": round(total_lat / total_cnt * 1000, 2) if total_cnt else 0.0,
            "verdicts": {k: int(v) for k, v in verdicts.items()},
        }

    def render(self) -> str:
        lines = []
        with self._lock:
            by_name: Dict[str, list] = defaultdict(list)
            for (name, labels), value in self._counters.items():
                by_name[name].append((labels, value))
            for name in sorted(by_name):
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                lines.append(f"# TYPE {name} counter")
                for labels, value in sorted(by_name[name]):
                    label_str = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
                    lines.append(f"{name}{{{label_str}}} {value:g}" if label_str else f"{name} {value:g}")

            hist_names = sorted({n for n, _ in self._hist_counts})
            for name in hist_names:
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                lines.append(f"# TYPE {name} histogram")
                for (n, route), counts in sorted(self._hist_counts.items()):
                    if n != name:
                        continue
                    r = _escape(route)
                    for bound, c in zip(LATENCY_BUCKETS, counts):
                        lines.append(f'{name}_bucket{{route="{r}",le="{bound:g}"}} {c}')
                    lines.append(f'{name}_bucket{{route="{r}",le="+Inf"}} {self._hist_total[(n, route)]}')
                    lines.append(f'{name}_sum{{route="{r}"}} {self._hist_sum[(n, route)]:.6f}')
                    lines.append(f'{name}_count{{route="{r}"}} {self._hist_total[(n, route)]}')
        return "\n".join(lines) + "\n"


metrics = Metrics()
metrics.describe("phishsentinel_http_requests_total", "HTTP requests by method, route and status")
metrics.describe("phishsentinel_http_request_duration_seconds", "HTTP request latency by route")
metrics.describe("phishsentinel_verdicts_total", "Verdicts produced, by verdict and input type")
metrics.describe("phishsentinel_detector_errors_total", "Detector failures that were degraded gracefully")
metrics.describe("phishsentinel_cache_events_total", "URL-analysis cache hits and misses")
metrics.describe("phishsentinel_list_hits_total", "Allow/deny list matches")
