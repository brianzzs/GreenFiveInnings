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



async def get_team_stats_summary(team_id: int, num_days: int) -> Dict:
    """Fetches game data and calculates NRFI, F5 Overs, F5 ML Results, and Win % for a team over N days."""
    try:
        game_ids = await schedule_service.fetch_and_cache_game_ids_span(team_id, num_days)
        
        if not game_ids:
            return { 
                "results": [],
                "nrfi": 0.0,
                "win_percentage": 0.0,
                "over1_5F5": 0.0,
                "over2_5F5": 0.0,
            }

        game_details = await fetch_game_details_batch(game_ids)

        first_inning_runs_list = [] 
        team_runs_f5_list = [] 
        moneyline_results_f5 = [] 

        for game in game_details:
            live_data = game.get("liveData", {})
            linescore = live_data.get("linescore", {})
            innings = linescore.get("innings", [])
            game_data = game.get("gameData", {})
            teams_data = game_data.get("teams", {})
            away_team_data = teams_data.get("away", {})
            home_team_data = teams_data.get("home", {})
            probable_pitchers = game_data.get("probablePitchers", {})
            players_data = game_data.get("players", {})
            datetime_data = game_data.get("datetime", {})

            if not innings: # Skip game if no innings data
                continue
                
            if innings:
                first_inning = innings[0]
                fi_home_runs = first_inning.get("home", {}).get("runs")
                fi_away_runs = first_inning.get("away", {}).get("runs")
                if fi_home_runs is not None and fi_away_runs is not None:
                    first_inning_runs_list.append((fi_home_runs, fi_away_runs))
            
            # F5 Overs calculation: Sum team runs in first 5 innings
            f5_innings = innings[:5]
            team_runs_f5 = 0
            is_home_team = home_team_data.get("id") == team_id
            for inning in f5_innings:
                inning_data = inning.get("home" if is_home_team else "away", {})
                inning_runs = inning_data.get("runs")
                if inning_runs is not None:
                    team_runs_f5 += inning_runs
            team_runs_f5_list.append(team_runs_f5)

            # F5 Moneyline calculation: Gather data needed
            home_pitcher = probable_pitchers.get("home", {"fullName": "TBD", "id": "TBD"})
            away_pitcher = probable_pitchers.get("away", {"fullName": "TBD", "id": "TBD"})
            
            home_pitcher_id_str = str(home_pitcher.get("id"))
            away_pitcher_id_str = str(away_pitcher.get("id"))

            # Safely get pitcher hand, default to TBD
            home_pitcher_hand = players_data.get(f"ID{home_pitcher_id_str}", {}).get("pitchHand", {}).get("code", "TBD") if home_pitcher_id_str != "TBD" else "TBD"
            away_pitcher_hand = players_data.get(f"ID{away_pitcher_id_str}", {}).get("pitchHand", {}).get("code", "TBD") if away_pitcher_id_str != "TBD" else "TBD"

            away_runs_f5_list = [inning.get("away", {}).get("runs") for inning in f5_innings]
            home_runs_f5_list = [inning.get("home", {}).get("runs") for inning in f5_innings]

            # Filter out None values before summing
            away_total_runs_f5 = sum(r for r in away_runs_f5_list if r is not None)
            home_total_runs_f5 = sum(r for r in home_runs_f5_list if r is not None)

            moneyline_results_f5.append(
                {
                    "game_date": datetime_data.get("originalDate", "TBD"),
                    "away_team": {
                        "id": away_team_data.get("id"),
                        "name": TEAM_NAMES.get(away_team_data.get("id"), "TBD"),
                        "runs": [r if r is not None else 'N/A' for r in away_runs_f5_list], # Handle potential None
                        "probable_pitcher": {
                            "name": away_pitcher.get("fullName", "TBD"),
                            "id": away_pitcher.get("id", "TBD"),
                            "hand": away_pitcher_hand,
                        },
                        "total_runs": away_total_runs_f5,
                    },
                    "home_team": {
                        "id": home_team_data.get("id"),
                        "name": TEAM_NAMES.get(home_team_data.get("id"), "TBD"),
                        "runs": [r if r is not None else 'N/A' for r in home_runs_f5_list], 
                        "probable_pitcher": {
                            "name": home_pitcher.get("fullName", "TBD"),
                            "id": home_pitcher.get("id", "TBD"),
                            "hand": home_pitcher_hand,
                        },
                        "total_runs": home_total_runs_f5,
                    },
                }
            )

        nrfi_occurrence_calc = (
            sum(1 for home_runs, away_runs in first_inning_runs_list if home_runs == 0 and away_runs == 0)
            / len(first_inning_runs_list)
            * 100
            if first_inning_runs_list
            else 0
        )

        over_1_5_calc = (
            sum(1 for runs in team_runs_f5_list if runs >= 1.5) / len(team_runs_f5_list) * 100
            if team_runs_f5_list
            else 0
        )
        over_2_5_calc = (
            sum(1 for runs in team_runs_f5_list if runs >= 2.5) / len(team_runs_f5_list) * 100
            if team_runs_f5_list
            else 0
        )
        
        win_percentage_calc = calculate_win_percentage(moneyline_results_f5, team_id)

        return {
            "results": moneyline_results_f5,
            "nrfi": round(nrfi_occurrence_calc, 2),
            "win_percentage": round(win_percentage_calc, 2), 
            "over1_5F5": round(over_1_5_calc, 2),
            "over2_5F5": round(over_2_5_calc, 2),
        }

    except Exception as e:
        print(f"Error calculating team stats summary for team {team_id}: {e}")
        return {
            "results": [],
            "nrfi": 0.0,
            "win_percentage": 0.0,
            "over1_5F5": 0.0,
            "over2_5F5": 0.0,
        } 