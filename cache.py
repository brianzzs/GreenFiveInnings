import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class BoundedCache:
    def __init__(self, maxsize: int, default_ttl: Optional[int] = None):
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry["expires_at"] is not None and entry["expires_at"] <= time.time():
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> Any:
        effective_ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl is not None else None
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = {"value": value, "expires_at": expires_at}
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)
        return value

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def get_ttl_cache(key: str) -> Optional[Any]:
    return _ttl_cache.get(key)


def set_ttl_cache(key: str, value: Any, ttl_seconds: int) -> Any:
    return _ttl_cache.set(key, value, ttl_seconds)


_ttl_cache = BoundedCache(maxsize=256)
GAME_CACHE = BoundedCache(maxsize=512)
SCHEDULE_CACHE = BoundedCache(maxsize=64)
