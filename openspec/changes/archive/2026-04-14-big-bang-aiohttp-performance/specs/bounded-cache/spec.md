## ADDED Requirements

### Requirement: Bounded cache with max size
The system SHALL provide a `BoundedCache` class that enforces a configurable maximum number of entries. When the maximum is exceeded, the least-recently-used entry SHALL be evicted.

#### Scenario: Cache evicts LRU when full
- **WHEN** the cache is at max capacity and a new entry is added
- **THEN** the least-recently-accessed entry is removed before the new entry is stored

#### Scenario: Cache respects configured size
- **WHEN** a `BoundedCache` is created with `maxsize=512`
- **THEN** it holds at most 512 entries at any time

### Requirement: TTL-based expiration
Each cache entry SHALL have a configurable time-to-live. Expired entries SHALL be treated as cache misses on `get()` and removed.

#### Scenario: Expired entry returns miss
- **WHEN** a cached entry's TTL has elapsed and a `get()` is called for its key
- **THEN** the entry is removed and `None` is returned

#### Scenario: Fresh entry returns value
- **WHEN** a cached entry's TTL has not elapsed and a `get()` is called for its key
- **THEN** the stored value is returned

### Requirement: Periodic expired entry cleanup
The system SHALL periodically remove expired entries from the cache to reclaim memory, even if those keys are never accessed again.

#### Scenario: Cleanup runs on access
- **WHEN** a `get()` or `set()` operation occurs
- **THEN** expired entries encountered during the operation are removed

### Requirement: Thread-safe operations
All cache operations (`get`, `set`, `delete`) SHALL be thread-safe, using `threading.Lock`, to support Gunicorn's `gthread` worker model.

#### Scenario: Concurrent access from multiple threads
- **WHEN** two threads simultaneously call `get()` and `set()` on the same cache instance
- **THEN** no data corruption or race conditions occur

### Requirement: Replace all unbounded caches
The system SHALL replace `GAME_CACHE`, `SCHEDULE_CACHE`, and `TTL_CACHE` with instances of `BoundedCache`. Each replacement SHALL have an appropriate max size:
- `GAME_CACHE` → maxsize 512
- `SCHEDULE_CACHE` → maxsize 64
- `TTL_CACHE` → maxsize 256

#### Scenario: Game cache is bounded
- **WHEN** more than 512 unique game records are cached
- **THEN** the oldest entries are evicted automatically

#### Scenario: Existing cache consumers continue working
- **WHEN** service code calls `get_ttl_cache(key)` or `set_ttl_cache(key, value, ttl)`
- **THEN** behavior is identical to before but with bounded memory usage

### Requirement: Fix lru_cache on route handlers
The system SHALL remove `@lru_cache` decorators from Flask route handler functions. Caching SHALL be applied at the service layer instead, caching raw data rather than Flask `Response` objects.

#### Scenario: Route handler is not directly cached
- **WHEN** `get_schedule_route(team_id)` is called
- **THEN** no `@lru_cache` decorator is present on the route function; caching happens inside `schedule_service.get_schedule_for_team()`

#### Scenario: Service-layer cache stores data
- **WHEN** `schedule_service.get_schedule_for_team(team_id)` is called twice with the same `team_id`
- **THEN** the second call returns cached data from `@lru_cache` on the service function
