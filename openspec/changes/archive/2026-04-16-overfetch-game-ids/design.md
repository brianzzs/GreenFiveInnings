## Context

The team stats pipeline in `game_service.py:_get_team_stats_summary_by_innings` fetches N game IDs from `schedule_service.fetch_last_n_completed_game_ids`, then processes them through a multi-stage filter:

1. `fetch_game_details_batch` — drops games where the MLB API returns null
2. `valid_game_details` filter — drops games missing `gameData` or `liveData`
3. Linescore check — drops games with no innings data
4. Team ID check — drops games with missing team IDs

Each filter silently discards games. The reported `games_analyzed` reflects only games surviving all stages, which is frequently less than the requested count (e.g., 9 instead of 10).

## Goals / Non-Goals

**Goals:**
- Ensure `games_analyzed` reliably matches the requested `num_games` parameter
- Minimal code change — single function modification
- No changes to the public API response shape

**Non-Goals:**
- Refactoring the filtering pipeline
- Fixing player endpoints (different architecture)
- Adding retry logic for individual game fetches
- Caching improvements

## Decisions

### Decision 1: Over-fetch by a fixed buffer of 3

Request `num_games + 3` from `fetch_last_n_completed_game_ids`, then truncate the processed results to `num_games` after filtering.

**Alternatives considered:**
- **Fetch-filter-refetch loop**: Fetch N, count survivors, if short then fetch more. More precise but adds complexity (need `exclude_ids` param, multiple round trips, loop control). Overkill given the typical drop rate is 0-1 games.
- **Over-fetch by percentage (e.g., 20%)**: Scales with N, but harder to reason about. A fixed buffer of 3 covers the common case (0-1 drops) with headroom.

**Rationale**: Simple, predictable, and covers the observed drop pattern. The performance cost of 3 extra game detail fetches is negligible compared to the existing batch fetch.

### Decision 2: Truncate results list, not just the count

After processing all valid games, slice the `detailed_game_results` list and recalculate all stats (percentages, counts) against only the first `num_games` entries. This ensures the reported stats match the requested window exactly.

**Rationale**: If we over-fetched 13 and got 11 valid games back, reporting stats on all 11 would be incorrect — the user asked for 10, so we use only the 10 most recent valid games.

### Decision 3: Apply buffer only in `_get_team_stats_summary_by_innings`

The change is isolated to the call site in `game_service.py`. `fetch_last_n_completed_game_ids` itself is unchanged — it remains a general-purpose "fetch N games" function.

**Rationale**: Keeps `schedule_service` clean. The buffer is a consumer-side concern specific to the stats pipeline that knows about the filtering.

## Risks / Trade-offs

- **[Slightly more API calls]** → Fetching 3 extra games means 3 more calls to the MLB game data endpoint. Mitigated by caching in `GAME_CACHE` and `fetch_single_game_details` — if the extra games were recently fetched, they're cache hits.
- **[Edge case: early season with few games]** → If a team has only played 8 games and we request 10, `fetch_last_n_completed_game_ids(13)` still returns only 8. No regression — same behavior as before, just returns all available games.
- **[Buffer too small for extreme cases]** → If more than 3 games in a batch have bad data, we'd still come up short. Extremely unlikely given the observed 0-1 drop pattern. Can increase buffer later if needed.
