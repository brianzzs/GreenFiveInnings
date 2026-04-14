## Context

GreenFiveInnings is a Flask API running on Railway with 2 Gunicorn workers (gthread, 4 threads each). All external HTTP calls to MLB Stats API and Open-Meteo use the blocking `requests` library, wrapped in `asyncio.to_thread` where async is needed. In-memory caches are unbounded Python dicts that grow without eviction. Key symptoms:

- `/park-factors`: ~9s (sequential weather fetches for ~15 games)
- `/comparison/<id>`: ~9s (35-50 external API calls per request)
- RAM: ~800MB steady, spikes to 2GB
- `aiohttp` is already in `requirements.txt` but unused

## Goals / Non-Goals

**Goals:**
- `/park-factors` responds in <5s, `/comparison` in <4s
- RAM stays under 512MB steady-state with no unbounded growth
- All external HTTP calls use async I/O, eliminating thread-pool bottleneck
- Zero changes to API request/response contracts

**Non-Goals:**
- Redis or any external cache store
- New endpoints or changed response shapes
- Front-end changes
- Caching at the CDN/reverse-proxy level

## Decisions

### 1. Replace `requests` with `aiohttp` everywhere

**Decision**: Create a shared `aiohttp.ClientSession` managed as a Flask app-level resource, used by all HTTP calls in `mlb_stats_client` and `weather_client`.

**Rationale**: `asyncio.to_thread` offloads blocking I/O to a thread pool, but the pool size (4 threads) limits concurrency. With `aiohttp`, a single thread can handle hundreds of concurrent HTTP requests. `aiohttp` is already a dependency.

**Alternatives considered**:
- `httpx` with async support — additional dependency, `aiohttp` already installed
- Increase thread count — more threads = more memory per worker, doesn't solve the fundamental blocking issue

### 2. Session lifecycle: create on first use, close on app teardown

**Decision**: Lazily initialize a singleton `aiohttp.ClientSession` on first access. Register an `app.teardown_appcontext` hook to close it.

**Rationale**: Flask doesn't natively support async lifecycle hooks. Lazy init avoids needing to restructure the app factory. The session provides connection pooling and keep-alive across all requests.

### 3. Bounded TTL cache with periodic cleanup

**Decision**: Replace `GAME_CACHE`, `SCHEDULE_CACHE`, and `TTL_CACHE` with a single `BoundedCache` class that:
- Has a configurable max-size (evicts LRU when exceeded)
- Cleans up expired entries on every `get()` and via a periodic sweep
- Uses `threading.Lock` for thread safety (gunicorn gthread uses threads)

**Rationale**: Current dicts grow forever. A single abstraction reduces duplication and makes memory behavior predictable. Thread safety is needed because gthread workers share state within a process via module-level globals.

**Alternatives considered**:
- `cachetools.TTLCache` — solid library, but avoids adding a new dependency for something simple
- Per-cache-type classes — more code, same logic repeated

### 4. Parallelize park-factors weather fetches

**Decision**: Collect all weather fetch tasks into a list and `asyncio.gather()` them concurrently.

**Rationale**: Weather for each game is independent. Sequential fetches are the primary cause of the 9s `/park-factors` response time. With `aiohttp`, all 15 fetches can run simultaneously.

### 5. Fix `lru_cache` on route handlers

**Decision**: Move `@lru_cache` from route handlers to the underlying service functions, and ensure cached data (not Flask Response objects) is what gets stored.

**Rationale**: `@lru_cache` on `get_schedule_route()` caches the Flask `Response` object which is not pickle-safe and ties up memory. Caching at the service layer is cleaner and testable.

### 6. Gunicorn worker tuning

**Decision**: Switch from `gthread` to `gevent` workers (or increase thread count) once async migration is complete, since the blocking bottleneck is removed. Keep `--workers 2` initially and monitor.

**Rationale**: With async I/O, the thread pool is no longer the bottleneck. `gevent` or even a single-threaded async worker would suffice. But this is a tuning step, not a prerequisite.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `aiohttp` session not closed properly on worker shutdown | Register teardown hook; add atexit fallback |
| Mixed sync/async code paths during migration (some calls async, some still sync) | Migrate client modules first, then services. Keep `asyncio.to_thread` wrappers as bridge during transition |
| `statsapi` library is sync-only — can't use aiohttp for its internal calls | For functions that use `statsapi` directly (`get_game_data`, `get_schedule`, `lookup_player`), keep `asyncio.to_thread` wrappers but move to direct `aiohttp` calls for the MLB REST endpoints we already call directly (H2H, standings, player stats with season param) |
| Thread-safety of new bounded cache with gthread workers | Use `threading.Lock`; test under concurrent load |
| Session not available in non-request context (tests, CLI) | Provide a context manager or standalone session factory for off-request usage |

## Migration Plan

1. Implement `BoundedCache` and replace all cache dicts — deploy, verify RAM stabilizes
2. Create `aiohttp` session manager — deploy alongside existing `requests` calls
3. Migrate `weather_client` to `aiohttp` — deploy, verify `/park-factors` improvement
4. Parallelize park-factors weather loop — deploy, measure latency
5. Migrate `mlb_stats_client` direct HTTP calls to `aiohttp` — deploy
6. Migrate `statsapi` wrapper calls to use `aiohttp` for direct endpoints, keep `asyncio.to_thread` for library calls
7. Fix `lru_cache` placement
8. Tune Gunicorn configuration

Rollback: Each step is independently deployable. If a migration step causes issues, revert that specific commit. The old `requests` code can coexist with `aiohttp` during transition.
