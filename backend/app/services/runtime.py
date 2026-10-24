"""
Process-wide service singletons (cache, org lists, live event bus).
Kept in one tiny module so routers share the same instances.
"""
from app.config import CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS, LIST_REFRESH_SECONDS, MAX_SSE_SUBSCRIBERS
from app.services.cache import TTLCache
from app.services.events import EventBus
from app.services.lists import ListService


def _load_list_pairs():
    from app.db import crud
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        return crud.list_pairs(db)
    finally:
        db.close()


url_cache = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=CACHE_MAX_ENTRIES)
list_service = ListService(_load_list_pairs, refresh_seconds=LIST_REFRESH_SECONDS)
event_bus = EventBus(max_subscribers=MAX_SSE_SUBSCRIBERS)
