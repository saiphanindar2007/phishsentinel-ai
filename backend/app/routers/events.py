"""
PhishSentinel AI — Live verdict stream (Server-Sent Events)
---------------------------------------------------------------
GET /events/stream emits every verdict as it happens. The browser's
EventSource cannot send custom headers, so the dashboard consumes this
with fetch() streaming and passes X-API-Key normally.

The generator is synchronous (runs in Starlette's threadpool) with a
15s keepalive so proxies don't drop idle connections.
"""
import json
import queue

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.security import rate_limit, require_api_key
from app.services.runtime import event_bus

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(rate_limit), Depends(require_api_key)])


@router.get("/stream")
def stream():
    q = event_bus.subscribe()
    if q is None:
        raise HTTPException(status_code=503, detail="Too many live viewers. Try again shortly.")

    def gen():
        try:
            yield "retry: 3000\n\n: connected\n\n"
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"event: verdict\ndata: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
