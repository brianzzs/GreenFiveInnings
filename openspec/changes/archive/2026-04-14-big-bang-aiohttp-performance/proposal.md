## Why

The `/park-factors` and `/comparison` endpoints take ~9 seconds to respond, RAM spikes to 2GB on Railway, and throughput is gated by a thread pool of 4. All external HTTP calls use blocking `requests` wrapped in `asyncio.to_thread`, which caps concurrency and wastes memory. A full migration to `aiohttp` with proper cache management will cut latency, stabilize memory, and reduce infrastructure cost.

## What Changes

- Replace all `requests` calls in `mlb_stats_client` and `weather_client` with `aiohttp` async sessions, removing `asyncio.to_thread` wrappers
- Parallelize weather fetches in `park_factor_service` (currently sequential across ~15 games)
- Add bounded, self-evicting caches to replace unbounded `dict` caches (`GAME_CACHE`, `SCHEDULE_CACHE`, `TTL_CACHE`)
- Fix `lru_cache` misuse on route handlers (caching Flask `Response` objects instead of data)
- Add periodic TTL cache cleanup to reclaim memory from expired entries
- Tune Gunicorn worker configuration for async workload

## Capabilities

### New Capabilities
- `async-http-client`: Centralized `aiohttp` session management with connection pooling and shared timeouts, replacing all `requests` usage
- `bounded-cache`: Size-limited, auto-evicting in-memory caches with periodic TTL cleanup, replacing unbounded dicts
- `parallel-park-factors`: Concurrent weather and schedule fetches for the park-factors endpoint

### Modified Capabilities

_(No existing specs to modify — this is the first spec-driven change.)_

## Non-goals

- No Redis or external cache store — keep everything in-process for now
- No API contract changes — request/response shapes stay identical
- No new endpoints or features
- No changes to the MLB Stats API or Open-Meteo API integration logic beyond making calls async
- No front-end changes

## Impact

- **Code**: `mlb_stats_client.py`, `weather_client.py`, `cache.py`, `park_factor_service.py`, `comparison_service.py`, `schedule_service.py`, `player_service.py`, `game_service.py`, `Dockerfile`, `__init__.py`
- **Dependencies**: Removes `requests` usage at runtime (keep in requirements for non-async fallbacks if needed); `aiohttp` already in requirements
- **Infrastructure**: Railway — should allow downscaling dyno size due to lower RAM and faster responses
- **Risk**: High-touch refactor across all external call sites; needs thorough regression testing
