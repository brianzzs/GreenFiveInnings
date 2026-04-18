## Context

The app already fetches batter-vs-pitcher head-to-head (H2H) stats in the comparison endpoint via `mlb_stats_client.get_player_h2h_stats`, which calls `statsapi.mlb.com/api/v1/people/{batterId}/stats?stats=vsTeamTotal&group=hitting&opposingPlayerId={pitcherId}`. This is cached per batter-pitcher pair with `@alru_cache(512)`. The comparison endpoint runs H2H for a single game's lineups and embeds the results per-player. What's missing is an aggregated view across all games for the day.

## Goals / Non-Goals

**Goals:**
- Single endpoint returning all batter-vs-pitcher matchups for today, sorted by AVG descending
- Minimum 2 AB filter to remove small-sample noise
- Tiebreak by more ABs first
- Frontend-friendly response with batter/pitcher identity, team context, and H2H line stats
- Good performance: parallel fetching, leverage existing caches

**Non-Goals:**
- Historical "best matchups on this date" across seasons
- Pitcher-vs-batter (how pitchers perform against specific batters)
- Live in-game updates — this is a pre-game tool

## Decisions

### 1. New service + route (not extending comparison_service)
`matchup_service.py` and `matchup.py` route. The comparison service is game-scoped and returns nested team-vs-team structure. This feature flattens across all games into a single sorted list — different shape, different purpose. Sharing a service would add coupling without benefit.

### 2. Lineup resolution: same pattern as comparison
Confirmed boxscore lineup → `get_last_game_lineup()` fallback. This is the proven pattern already in `_fetch_game_context`. No need to invent something new.

### 3. H2H fetching: batch all games, gather in parallel
For each game, build H2H task list (same pattern as `_build_h2h_tasks`). Then `asyncio.gather` all tasks across all games at once. With `@alru_cache(512)` on the H2H client, repeat batter-pitcher pairs across requests are free.

### 4. Sorting: AVG descending, ties by AB descending
Parse AVG as float for comparison. Matchups with null/undefined AVG (e.g. 0-for-N where MLB returns ".000") still sort correctly at the bottom.

### 5. Response caching: TTL cache same as today's schedule
Use the existing TTL cache pattern (`get_ttl_cache`/`set_ttl_cache`) with a short TTL (~60s) since lineups and pitcher assignments change during the day.

## Risks / Trade-offs

- **[H2H API volume]** ~270 calls per request on a full 15-game slate → Mitigated by `@alru_cache(512)` on H2H client; warm cache means most calls are instant. First cold call will be slow (~2-3s per H2H call, ~30s total with parallelism). → Mitigation: TTL cache the entire response.
- **[Stale lineups]** If today's lineups aren't posted yet, fallback to last game. Batters may differ from actual lineup. → Acceptable tradeoff; data refreshes as lineups post.
- **[AVG precision]** MLB API returns AVG as string (e.g. ".333"). Parsing to float for sorting is straightforward but needs to handle edge cases like ".---" or null.
