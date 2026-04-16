## 1. Over-fetch game IDs

- [x] 1.1 In `_get_team_stats_summary_by_innings` (`app/services/game_service.py`), change the call to `fetch_last_n_completed_game_ids` from `num_games` to `num_games + 3`
- [x] 1.2 Store the original `num_games` in a local variable (e.g., `requested_games`) before the over-fetch, so truncation uses the correct count

## 2. Truncate processed results

- [x] 2.1 After the processing loop, truncate all accumulated stat lists (`game_nrfi_list`, `team_nrfi_list`, `team_runs_by_window_list`, `game_total_list`, `run_line_diffs`, `moneyline_results_for_calc`) to at most `requested_games` entries
- [x] 2.2 If `include_details` is true, truncate `detailed_game_results` to at most `requested_games` entries
- [x] 2.3 Clamp `games_processed_count` to at most `requested_games`

## 3. Verification

- [x] 3.1 Run syntax check — Python compile verified OK
- [x] 3.2 Clean compile confirmed
- [x] 3.3 Over-fetch logic verified (13 IDs fetched for num_games=10 request)
- [x] 3.4 Truncation logic verified for multiple list types at requested_games boundary
