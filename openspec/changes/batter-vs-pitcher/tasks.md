## 1. Service Layer

- [x] 1.1 Create `app/services/matchup_service.py` with `get_best_matchups()` that fetches today's schedule and iterates over each game
- [x] 1.2 Implement per-game lineup resolution: confirmed boxscore lineup → `get_last_game_lineup()` fallback
- [x] 1.3 Build H2H task list for each game (away batters vs home pitcher, home batters vs away pitcher) and gather in parallel with `asyncio.gather`
- [x] 1.4 Filter matchups with fewer than 2 ABs
- [x] 1.5 Sort by AVG descending, ties broken by more ABs; parse AVG safely (handle null, ".---", ".000")
- [x] 1.6 Build response objects with batter info, pitcher info, game_id, and H2H stats
- [x] 1.7 Add TTL cache (~60s) around the full response using existing `get_ttl_cache`/`set_ttl_cache` pattern

## 2. API Layer

- [x] 2.1 Create `app/api/matchup.py` with Blueprint and `GET /best-matchups/today` route
- [x] 2.2 Register the matchup blueprint in the Flask app factory (`app/__init__.py` or `asgi.py`)

## 3. Verification

- [x] 3.1 Run `bun run typecheck` (or Python equivalent) to verify no import or type errors
- [x] 3.2 Run the server and call `GET /best-matchups/today` to verify response shape and sorting
- [x] 3.3 Run `bun run lint:file` on new files
