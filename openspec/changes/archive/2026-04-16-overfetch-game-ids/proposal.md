## Why

When requesting "last N games" for team stats, the API frequently returns fewer than N results (e.g., 9 instead of 10, 14 instead of 15). The pipeline fetches exactly N game IDs from `schedule_service`, but subsequent filters in `game_service` silently drop games that have incomplete MLB API data (missing `liveData`, no linescore, no innings, missing team IDs). There is no compensation mechanism to fetch additional games to replace the dropped ones.

## What Changes

- Over-fetch game IDs from `schedule_service.fetch_last_n_completed_game_ids` by a buffer of 3 (`num_games + 3`) so that after the multi-stage filtering pipeline in `_get_team_stats_summary_by_innings`, the final `games_analyzed` count reliably meets the requested `num_games`.
- After processing, truncate the results list and recalculate all percentages/stats against the requested `num_games` count (not the over-fetched count).

## Capabilities

### New Capabilities

- `game-overfetch-buffer`: Adds an over-fetch buffer when fetching game IDs for team stats, ensuring enough games survive the filtering pipeline to meet the requested count.

### Modified Capabilities

_(none)_

## Impact

- **Affected code**: `app/services/game_service.py` — `_get_team_stats_summary_by_innings` function, specifically the call to `fetch_last_n_completed_game_ids` and the result truncation logic.
- **Affected endpoints**: All team stats endpoints (`/comparison/<game_id>`, `/comparison/full-game/<game_id>`, `/schedule/team-stats/<team_id>/<num_games>`, `/schedule/team-full-stats/<team_id>/<num_games>`) — response payloads remain the same shape, but `games_analyzed` will more reliably match the requested count.
- **Performance**: Slight increase — fetching 3 extra games per request. Acceptable trade-off for correctness.
- **Player endpoints**: Explicitly NOT changed.

## Non-goals

- Refactoring the filtering pipeline to be more tolerant of incomplete data.
- Adding retry/fallback logic for individual failed game detail fetches.
- Modifying the player stats endpoints (`get_player_recent_stats`, `get_player_betting_stats`).
- Changing the public API contract (response shape stays the same).
