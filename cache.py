import time
from typing import Dict, List, Any, Optional

GAME_CACHE: Dict[int, Any] = {}
SCHEDULE_CACHE: Dict[str, List[Any]] = {}
TTL_CACHE: Dict[str, Dict[str, Any]] = {}


def get_ttl_cache(key: str) -> Optional[Any]:
    entry = TTL_CACHE.get(key)
    if not entry:
        return None

    if entry["expires_at"] <= time.time():
        TTL_CACHE.pop(key, None)
        return None

    return entry["value"]


def set_ttl_cache(key: str, value: Any, ttl_seconds: int) -> Any:
    TTL_CACHE[key] = {
        "value": value,
        "expires_at": time.time() + ttl_seconds,
    }
    return value
