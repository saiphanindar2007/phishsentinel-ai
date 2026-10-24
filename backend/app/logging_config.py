"""
PhishSentinel AI — Structured logging
-----------------------------------------
JSON logs (one object per line) in production so any log pipeline
(CloudWatch, Loki, ELK, Datadog) can index them; readable text in
development. Every record carries the current request's id, so a single
user complaint can be traced across every log line it produced.
"""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    _SKIP = {"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info",
             "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread",
             "threadName", "processName", "process", "message", "taskName", "request_id"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for k, v in record.__dict__.items():           # `extra={...}` fields
            if k not in self._SKIP and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        JsonFormatter() if json_logs
        else logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # We emit our own structured access log; silence uvicorn's duplicate.
    logging.getLogger("uvicorn.access").disabled = True
