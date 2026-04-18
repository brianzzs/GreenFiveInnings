## Why

Bettors and analysts need to see which batters have historically performed well (or poorly) against today's opposing pitchers, all in one view. Today this data exists per-game inside the comparison endpoint, but there's no aggregated, sorted view across all of the day's matchups. A dedicated endpoint gives the front-end a single call to power a "Best Matchups" feature.

## What Changes

- Add a new `GET /best-matchups/today` endpoint that returns all batter-vs-pitcher H2H matchups across today's scheduled games
- For each game: fetch lineups (confirmed or last-game fallback), get H2H stats for each batter vs the opposing pitcher
- Filter out matchups with fewer than 2 career at-bats
- Sort results by AVG descending; ties broken by more ABs first
- Return a flat, frontend-ready list with batter info, pitcher info, game context, and full H2H stats

## Capabilities

### New Capabilities
- `best-matchups`: Aggregated daily view of batter-vs-pitcher H2H stats across all scheduled games, sorted by AVG with a minimum 2 AB threshold

### Modified Capabilities
<!-- No existing specs require changes -->

## Impact

- **New files**: `app/services/matchup_service.py`, `app/api/matchup.py`
- **API surface**: One new public endpoint
- **Dependencies**: Reuses existing `mlb_stats_client.get_player_h2h_stats`, `schedule_service.get_today_schedule`, `helpers.extract_lineup`, and `schedule_service.get_last_game_lineup`
- **Performance**: Up to ~15 games × ~18 batters = ~270 H2H API calls per request (mitigated by existing `@alru_cache` on H2H endpoint and schedule-level TTL caching)
