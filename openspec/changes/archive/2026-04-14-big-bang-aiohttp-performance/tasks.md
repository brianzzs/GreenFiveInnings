## 1. Bounded Cache

- [x] 1.1 Implement `BoundedCache` class in `cache.py` with `maxsize`, TTL expiration, LRU eviction, and `threading.Lock` for thread safety
- [x] 1.2 Replace `TTL_CACHE` dict and its `get_ttl_cache`/`set_ttl_cache` functions with `BoundedCache` instances (maxsize=256 for TTL)
- [x] 1.3 Replace `GAME_CACHE` dict with a `BoundedCache` instance (maxsize=512) in `cache.py`
- [x] 1.4 Replace `SCHEDULE_CACHE` dict with a `BoundedCache` instance (maxsize=64) in `cache.py`
- [x] 1.5 Update all consumers of `GAME_CACHE`, `SCHEDULE_CACHE`, `get_ttl_cache`, and `set_ttl_cache` to use the new `BoundedCache` API

## 2. Fix lru_cache Misuse

- [x] 2.1 Remove `@lru_cache` from `get_schedule_route()` in `schedule.py` — ensure caching lives in `schedule_service.get_schedule_for_team()`
- [x] 2.2 Remove `@lru_cache` from `get_next_schedule_route()` in `schedule.py` — ensure caching lives in `schedule_service.get_next_game_schedule_for_team()`
- [x] 2.3 Audit all `@lru_cache` and `@alru_cache` usage across services for correct placement (service layer, not route layer)

## 3. Async HTTP Client Infrastructure

- [x] 3.1 Create an `aiohttp` session manager module (e.g., `app/clients/http_session.py`) with lazy singleton init, Flask teardown hook registration, and an `atexit` fallback
- [x] 3.2 Register the session teardown hook in `app/__init__.py` inside `create_app()`
- [x] 3.3 Configure the session with connection pool limit of 20 and total timeout of 10 seconds

## 4. Migrate weather_client to aiohttp

- [x] 4.1 Rewrite `get_forecast_for_park()` in `weather_client.py` to use `aiohttp` async session instead of `requests`
- [x] 4.2 Add an async version `get_forecast_for_park_async()` or make the existing function async — update all callers
- [x] 4.3 Verify weather caching (TTL) still works correctly with async fetches

## 5. Migrate mlb_stats_client to aiohttp

- [x] 5.1 Rewrite direct MLB API HTTP calls (`get_player_h2h_stats`, `get_standings`, season-filtered `get_player_stats`, `get_player_info_with_stats`, `get_player_stat_data`) to use `aiohttp`
- [x] 5.2 Keep `asyncio.to_thread` wrappers for `statsapi` library functions (`get_game_data`, `get_schedule`, `lookup_player`, non-season `player_stats`)
- [x] 5.3 Update `_mlb_get` helper to use `aiohttp` for direct endpoint calls
- [x] 5.4 Remove `requests` imports from `mlb_stats_client.py` and `weather_client.py` once fully migrated
- [x] 5.5 Remove `requests` from `requirements.txt` if no other code uses it

## 6. Parallelize Park-Factors Weather Fetches

- [x] 6.1 Refactor the sequential `for game in raw_games` loop in `park_factor_service.get_today_park_factors()` to collect async weather tasks and run them with `asyncio.gather(return_exceptions=True)`
- [x] 6.2 Handle per-game weather failures gracefully — failed games still appear with stadium-baseline factors and `weather_unavailable` trait
- [x] 6.3 Make `get_today_park_factors()` an async function and update the route handler accordingly

## 7. Gunicorn Tuning

- [x] 7.1 Update `Dockerfile` CMD to increase thread count or switch worker class given async I/O (e.g., `--threads 8` or evaluate `gevent`)
- [x] 7.2 Adjust `--timeout` if needed — requests should complete much faster now

## 8. Testing & Verification

- [x] 8.1 Run existing test suite and fix any failures from the refactor
- [ ] 8.2 Manually test `/park-factors` cold-cache response time — verify under 5s
- [ ] 8.3 Manually test `/comparison/<game_id>` response time — verify under 4s
- [ ] 8.4 Monitor RAM usage under load — verify steady-state under 512MB
- [ ] 8.5 Verify weather data and park factor calculations produce identical results to pre-migration
