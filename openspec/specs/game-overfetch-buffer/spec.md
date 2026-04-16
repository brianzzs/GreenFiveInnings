## ADDED Requirements

### Requirement: Over-fetch game IDs by buffer
The system SHALL request `num_games + 3` game IDs from `schedule_service.fetch_last_n_completed_game_ids` when fetching games for team stats calculation, to compensate for games silently dropped during the filtering pipeline.

#### Scenario: Standard request for 10 games
- **WHEN** `_get_team_stats_summary_by_innings` is called with `num_games=10`
- **THEN** it SHALL call `fetch_last_n_completed_game_ids` requesting 13 game IDs

#### Scenario: One game dropped by filters
- **WHEN** 13 game IDs are fetched and 1 game is dropped by the filtering pipeline (missing linescore, etc.)
- **THEN** the system SHALL process the remaining 12 valid games and truncate to the first 10

#### Scenario: No games dropped by filters
- **WHEN** 13 game IDs are fetched and all pass the filtering pipeline
- **THEN** the system SHALL truncate results to the first 10 and ignore the 3 extra

### Requirement: Truncate results to requested count
The system SHALL truncate all processed results (stat lists, detailed game results) to at most `num_games` entries, ensuring `games_analyzed` does not exceed the requested count.

#### Scenario: More valid games than requested
- **WHEN** filtering produces more valid games than `num_games`
- **THEN** only the most recent `num_games` SHALL be used for stat calculation and returned in the response

#### Scenario: Fewer valid games than requested
- **WHEN** filtering produces fewer valid games than `num_games` even after the buffer
- **THEN** all valid games SHALL be used (same as current behavior — no artificial inflation)

### Requirement: Stats recalculated against truncated set
All computed statistics (percentages, counts, NRFI/YRFI rates, run percentages, win percentages) SHALL be calculated only from the truncated result set, not from the over-fetched superset.

#### Scenario: Percentage calculation with truncation
- **WHEN** 11 valid games are found for a `num_games=10` request
- **THEN** all percentages SHALL be calculated using only the 10 most recent games
