import asyncio
import aiohttp 
from typing import Dict, List, Any
from app.clients import mlb_stats_client
from cache import GAME_CACHE 
from functools import lru_cache
from app.services import schedule_service 
from app.utils.calculations import (
    TEAM_NAMES, 
    calculate_win_percentage,

)
import aiohttp


def fetch_and_cache_linescore(game_id: int) -> List[Dict]:
    """Fetches linescore data for a given game ID."""
    game = mlb_stats_client.get_game_data(game_pk=game_id)
    live_data = game.get("liveData", {})
    linescore = live_data.get("linescore", {})
    innings = linescore.get("innings", [])
    return innings

async def fetch_single_game_details(game_id: int) -> dict:
    """Fetches details for a single game, utilizing cache."""
    if game_id in GAME_CACHE:
        return GAME_CACHE[game_id]

    game_data = await mlb_stats_client.get_game_data_async(game_pk=game_id)
    GAME_CACHE[game_id] = game_data # Cache the result
    return game_data

async def fetch_game_details_batch(
    game_ids: List[int], 
) -> List[dict]:
    """Fetches details for a batch of games concurrently, utilizing cache."""
    tasks = [fetch_single_game_details(game_id) for game_id in game_ids]
    results = await asyncio.gather(*tasks)
    return [res for res in results if res is not None]

def get_processed_game_data(game_id: int) -> Dict:
    """Fetches and processes basic game data for a given game ID."""
    try:
        game = mlb_stats_client.get_game_data(game_pk=game_id)
        
        live_data = game.get("liveData", {})
        linescore = live_data.get("linescore", {})
        innings = linescore.get("innings", [])
        game_data = game.get("gameData", {})
        teams_data = game_data.get("teams", {})
        away_team_data = teams_data.get("away", {})
        home_team_data = teams_data.get("home", {})
        datetime_data = game_data.get("datetime", {})
        probable_pitchers = game_data.get("probablePitchers", {})
        away_pitcher_data = probable_pitchers.get("away", {})
        home_pitcher_data = probable_pitchers.get("home", {})

        away_team_id = away_team_data.get("id")
        home_team_id = home_team_data.get("id")
        game_datetime = datetime_data.get("dateTime")
        game_date = datetime_data.get("originalDate")
        away_pitcher_id = away_pitcher_data.get("id")
        home_pitcher_id = home_pitcher_data.get("id")

        away_team_runs = sum(inning.get("away", {}).get("runs", 0) for inning in innings)
        home_team_runs = sum(inning.get("home", {}).get("runs", 0) for inning in innings)

        return {
            "game_id": game_id,
            "away_team_id": away_team_id,
            "home_team_id": home_team_id,
            "game_datetime": game_datetime,
            "away_team_runs": away_team_runs,
            "home_team_runs": home_team_runs,
            "away_pitcher_id": away_pitcher_id, 
            "home_pitcher_id": home_pitcher_id, 
            "game_date": game_date,
        }

    except Exception as e:
        print(f"Error fetching or processing game data for game ID {game_id}: {e}")
        return None 



async def get_team_stats_summary(team_id: int, num_games: int) -> Dict:
    """Fetches game data for the last N completed games and calculates relevant stats."""
    try:
        game_ids = await schedule_service.fetch_last_n_completed_game_ids(team_id, num_games)

        if not game_ids:
            print(f"[get_team_stats_summary] No completed games found for team {team_id} in the searched range.")
            return {
                "games_analyzed": 0,
                "nrfi": 0.0, # Team NRFI
                "game_nrfi_percentage": 0.0, # Game NRFI
                "win_percentage_f5": 0.0,
                "over1_5F5": 0.0,
                "over2_5F5": 0.0,
                "results": []
            }

        game_details = await fetch_game_details_batch(game_ids)
        valid_game_details = [gd for gd in game_details if gd and gd.get("gameData") and gd.get("liveData")]

        if not valid_game_details:
             print(f"[get_team_stats_summary] Failed to fetch details for game IDs: {game_ids}")
             # Return defaults if no valid details fetched
             return {
                "games_analyzed": 0,
                "nrfi": 0.0,
                "game_nrfi_percentage": 0.0,
                "win_percentage_f5": 0.0,
                "over1_5F5": 0.0,
                "over2_5F5": 0.0,
                "results": []
            }

        game_nrfi_list = [] 
        team_nrfi_list = [] 
        team_runs_f5_list = []
        moneyline_results_f5_for_calc = []
        detailed_game_results = []
        games_processed_count = 0

        for game in valid_game_details:
            game_pk = game.get('gameData',{}).get('game', {}).get('pk', 'Unknown PK') # For logging
            live_data = game.get("liveData", {})
            linescore = live_data.get("linescore") 
            
            if not linescore or not linescore.get("innings") or not isinstance(linescore.get("innings"), list) or len(linescore["innings"]) == 0:
                print(f"[get_team_stats_summary] Skipping game {game_pk}: Missing or empty linescore/innings data.")
                continue
                
            innings = linescore["innings"] 
            game_data = game.get("gameData", {})
            teams_data = game_data.get("teams", {})
            away_team_data = teams_data.get("away", {})
            home_team_data = teams_data.get("home", {})
            datetime_data = game_data.get("datetime", {}) 
            probable_pitchers = game_data.get("probablePitchers", {})
            away_pitcher = probable_pitchers.get("away", {"fullName": "TBD", "id": "TBD"})
            home_pitcher = probable_pitchers.get("home", {"fullName": "TBD", "id": "TBD"})
            away_pitcher_hand = "TBD" 
            home_pitcher_hand = "TBD" 

            if not away_team_data.get('id') or not home_team_data.get('id'):
                print(f"[get_team_stats_summary] Skipping game {game_pk}: Missing team ID(s).")
                continue

            games_processed_count += 1
            is_home_team = home_team_data.get("id") == team_id

            final_scores = linescore.get('teams', {})
            full_away_runs = final_scores.get('away', {}).get('runs')
            full_home_runs = final_scores.get('home', {}).get('runs')

            first_inning = innings[0]
            fi_home_runs = first_inning.get("home", {}).get("runs")
            fi_away_runs = first_inning.get("away", {}).get("runs")
            if fi_home_runs is not None and fi_away_runs is not None:
                # Game NRFI (Neither team scored)
                game_nrfi_list.append(fi_home_runs == 0 and fi_away_runs == 0)
                # Team NRFI (This team didn't score)
                team_nrfi_list.append(fi_home_runs == 0 if is_home_team else fi_away_runs == 0)
            else:
                print(f"[get_team_stats_summary] Warning: Missing first inning runs data for game {game_pk}")


            f5_innings = innings[:min(len(innings), 5)] # Ensure we don't index out of bounds
            team_runs_f5 = 0
            runs_found_f5 = False
            for inning_num, inning in enumerate(f5_innings):
                inning_data = inning.get("home" if is_home_team else "away", {})
                inning_runs = inning_data.get("runs")
                if inning_runs is not None:
                    team_runs_f5 += inning_runs
                    runs_found_f5 = True
            
            if runs_found_f5:
                team_runs_f5_list.append(team_runs_f5)
            else:
                 print(f"[get_team_stats_summary] Warning: No F5 runs data found for team {team_id} game {game_pk}")

            away_total_runs_f5 = 0
            home_total_runs_f5 = 0
            away_runs_f5_list = [None] * 5 
            home_runs_f5_list = [None] * 5
            away_runs_found_f5 = False
            home_runs_found_f5 = False
            for i, inning in enumerate(f5_innings):
                away_inning_runs = inning.get("away", {}).get("runs")
                home_inning_runs = inning.get("home", {}).get("runs")
                if away_inning_runs is not None:
                    away_total_runs_f5 += away_inning_runs
                    away_runs_f5_list[i] = away_inning_runs 
                    away_runs_found_f5 = True
                if home_inning_runs is not None:
                    home_total_runs_f5 += home_inning_runs
                    home_runs_f5_list[i] = home_inning_runs
                    home_runs_found_f5 = True
            
            if away_runs_found_f5 and home_runs_found_f5:
                moneyline_results_f5_for_calc.append({
                    "away_team": {"id": away_team_data.get("id"), "total_runs": away_total_runs_f5},
                    "home_team": {"id": home_team_data.get("id"), "total_runs": home_total_runs_f5}
                })
            else:
                print(f"[get_team_stats_summary] Warning: Incomplete F5 runs data for score comparison in game {game_pk}")

            detailed_game_results.append({
                "game_date": datetime_data.get("originalDate", "TBD"),
                "game_pk": game_pk,
                "away_team": {
                    "id": away_team_data.get("id"),
                    "name": TEAM_NAMES.get(away_team_data.get("id"), "TBD"),
                    "runs": [r if r is not None else 'N/A' for r in away_runs_f5_list], # F5 runs per inning
                    "total_runs": away_total_runs_f5, # F5 total
                    "full_game_runs": full_away_runs, # Full game score
                    "probable_pitcher": { # Add pitcher info
                        "name": away_pitcher.get("fullName", "TBD"),
                        "id": away_pitcher.get("id", "TBD"),
                        "hand": away_pitcher_hand, 
                    },
                },
                "home_team": {
                    "id": home_team_data.get("id"),
                    "name": TEAM_NAMES.get(home_team_data.get("id"), "TBD"),
                    "runs": [r if r is not None else 'N/A' for r in home_runs_f5_list],
                    "total_runs": home_total_runs_f5,
                    "full_game_runs": full_home_runs,
                    "probable_pitcher": { # Add pitcher info
                        "name": home_pitcher.get("fullName", "TBD"),
                        "id": home_pitcher.get("id", "TBD"),
                        "hand": home_pitcher_hand, 
                    },
                },
            })

        game_nrfi_percentage_calc = (
            sum(1 for did_happen in game_nrfi_list if did_happen) 
            / len(game_nrfi_list) * 100
            if game_nrfi_list
            else 0.0
        )
        
        team_nrfi_percentage_calc = (
            sum(1 for did_happen in team_nrfi_list if did_happen) 
            / len(team_nrfi_list) * 100
            if team_nrfi_list
            else 0.0
        )

        over_1_5_calc = (
            sum(1 for runs in team_runs_f5_list if runs >= 1.5) / len(team_runs_f5_list) * 100
            if team_runs_f5_list
            else 0.0
        )
        over_2_5_calc = (
            sum(1 for runs in team_runs_f5_list if runs >= 2.5) / len(team_runs_f5_list) * 100
            if team_runs_f5_list
            else 0.0
        )

        win_percentage_f5_calc = calculate_win_percentage(moneyline_results_f5_for_calc, team_id)

        detailed_game_results.sort(key=lambda x: x.get('game_date', '0000-00-00'), reverse=True)

        return {
            "games_analyzed": games_processed_count, 
            "nrfi": round(team_nrfi_percentage_calc, 2),
            "game_nrfi_percentage": round(game_nrfi_percentage_calc, 2),
            "win_percentage_f5": round(win_percentage_f5_calc, 2),
            "over1_5F5": round(over_1_5_calc, 2),
            "over2_5F5": round(over_2_5_calc, 2),
            "results": detailed_game_results
        }

    except Exception as e:
        print(f"Error calculating team stats summary for team {team_id} over last {num_games} games: {e}")
        import traceback
        traceback.print_exc()
        return {
            "games_analyzed": 0,
            "error": f"Error calculating stats: {str(e)}",
            "nrfi": 0.0,
            "game_nrfi_percentage": 0.0,
            "win_percentage_f5": 0.0,
            "over1_5F5": 0.0,
            "over2_5F5": 0.0,
            "results": []
        } 