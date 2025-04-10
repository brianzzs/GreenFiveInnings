import asyncio
import datetime
from typing import Dict, Any, List, Optional
from app.services import game_service, player_service, schedule_service
from app.clients import mlb_stats_client
from app.utils.calculations import TEAM_NAMES
from app.utils import helpers

async def get_game_comparison(game_id: int, lookback_games: int = 10) -> Dict[str, Any]:
    """
    Generates a comparison between two teams for a specific game,
    including lineups with relevant H2H stats and team stats based on recent games.
    """
    try:
        raw_game_data = await mlb_stats_client.get_game_data_async(game_id)
        game_data = raw_game_data.get('gameData', {})
        live_data = raw_game_data.get('liveData', {})
        boxscore_data = live_data.get('boxscore', {})
        teams_info = game_data.get('teams', {})
        away_team_info = teams_info.get('away', {})
        home_team_info = teams_info.get('home', {})
        away_team_id = away_team_info.get('id')
        home_team_id = home_team_info.get('id')
        away_record_data = away_team_info.get('leagueRecord', {})
        home_record_data = home_team_info.get('leagueRecord', {})
        away_record_str = f"{away_record_data.get('wins', 0)}-{away_record_data.get('losses', 0)}"
        home_record_str = f"{home_record_data.get('wins', 0)}-{home_record_data.get('losses', 0)}"
        datetime_info = game_data.get('datetime', {})
        venue_info = game_data.get('venue', {})
        status_info = game_data.get('status', {})
        current_year = str(datetime.datetime.now().year)


        pitcher_details = player_service.fetch_and_cache_pitcher_info(game_id, raw_game_data)
        away_pitcher_id = pitcher_details.get('awayPitcherID')
        home_pitcher_id = pitcher_details.get('homePitcherID')


        away_lineup = helpers.extract_lineup(boxscore_data, 'away') 
        home_lineup = helpers.extract_lineup(boxscore_data, 'home')
        
        away_lineup_status = "Confirmed"
        home_lineup_status = "Confirmed"

        if away_lineup is None:
            print(f"[Comparison] Away lineup missing for game {game_id}. Fetching last lineup for team {away_team_id}...")
            away_lineup = await schedule_service.get_last_game_lineup(away_team_id)
            if away_lineup is not None:
                away_lineup_status = "Expected"
            else:
                print(f"[Comparison] Could not fetch last lineup for away team {away_team_id}.")
                away_lineup = []
                away_lineup_status = "Unavailable" 

        if home_lineup is None:
            print(f"[Comparison] Home lineup missing for game {game_id}. Fetching last lineup for team {home_team_id}...")
            home_lineup = await schedule_service.get_last_game_lineup(home_team_id)
            if home_lineup is not None:
                home_lineup_status = "Expected"
            else:
                print(f"[Comparison] Could not fetch last lineup for home team {home_team_id}.")
                home_lineup = []
                home_lineup_status = "Unavailable" 



        tasks_to_run = []

        tasks_to_run.append(game_service.get_team_stats_summary(away_team_id, lookback_games))
        tasks_to_run.append(game_service.get_team_stats_summary(home_team_id, lookback_games))

        away_lineup_h2h_task_indices = {} 
        home_lineup_h2h_task_indices = {} 

        if home_pitcher_id and home_pitcher_id != "TBD":
            for i, player in enumerate(away_lineup):
                player_id = player.get('id')
                if player_id:
                    tasks_to_run.append(asyncio.to_thread(mlb_stats_client.get_player_h2h_stats, player_id, home_pitcher_id))
                    away_lineup_h2h_task_indices[player_id] = len(tasks_to_run) - 1

        if away_pitcher_id and away_pitcher_id != "TBD":
            for i, player in enumerate(home_lineup):
                player_id = player.get('id')
                if player_id:
                    tasks_to_run.append(asyncio.to_thread(mlb_stats_client.get_player_h2h_stats, player_id, away_pitcher_id))
                    home_lineup_h2h_task_indices[player_id] = len(tasks_to_run) - 1


        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)


        away_summary = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0]), "games_analyzed": 0}
        home_summary = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1]), "games_analyzed": 0}

        away_pitcher_era = pitcher_details.get("awayPitcherERA", "N/A")
        home_pitcher_era = pitcher_details.get("homePitcherERA", "N/A")

        default_h2h = {"PA": "N/A"} 

        away_lineup_with_h2h = []
        for player in away_lineup:
            player_copy = player.copy() 
            player_id = player_copy.get('id')
            task_index = away_lineup_h2h_task_indices.get(player_id)

            if task_index is not None:
                h2h_result = results[task_index]
                if isinstance(h2h_result, Exception):
                    player_copy['h2h_stats'] = {"error": str(h2h_result)}
                elif h2h_result is None: 
                    player_copy['h2h_stats'] = {"error": "Fetch/Parse Failed"}
                else: 
                    player_copy['h2h_stats'] = h2h_result
            else: 
                player_copy['h2h_stats'] = default_h2h.copy() 
            away_lineup_with_h2h.append(player_copy)


        home_lineup_with_h2h = []
        for player in home_lineup:
            player_copy = player.copy()
            player_id = player_copy.get('id')
            task_index = home_lineup_h2h_task_indices.get(player_id)

            if task_index is not None:
                h2h_result = results[task_index]
                if isinstance(h2h_result, Exception):
                    player_copy['h2h_stats'] = {"error": str(h2h_result)}
                elif h2h_result is None:
                    player_copy['h2h_stats'] = {"error": "Fetch/Parse Failed"}
                else:
                    player_copy['h2h_stats'] = h2h_result
            else:
                player_copy['h2h_stats'] = default_h2h.copy()
            home_lineup_with_h2h.append(player_copy)


        comparison_data = {
            "game_info": {
                "game_id": game_id,
                "game_datetime": datetime_info.get('officialDate') or datetime_info.get('dateTime'),
                "status": status_info.get('abstractGameState', 'Unknown'),
                "venue": venue_info.get('name', 'TBD'),
                "away_team": {
                    "id": away_team_id,
                    "name": TEAM_NAMES.get(away_team_id, away_team_info.get('name', 'TBD')),
                    "record": away_record_str,
                    "lineup": away_lineup_with_h2h,
                    "lineup_status": away_lineup_status
                },
                "home_team": {
                    "id": home_team_id,
                    "name": TEAM_NAMES.get(home_team_id, home_team_info.get('name', 'TBD')),
                    "record": home_record_str,
                    "lineup": home_lineup_with_h2h,
                    "lineup_status": home_lineup_status
                },
                "away_pitcher": {
                    "id": away_pitcher_id,
                    "name": pitcher_details.get('awayPitcher', 'TBD'),
                    "hand": pitcher_details.get('awayPitcherHand', 'TBD'),
                    "season_era": away_pitcher_era
                },
                "home_pitcher": {
                    "id": home_pitcher_id,
                    "name": pitcher_details.get('homePitcher', 'TBD'),
                    "hand": pitcher_details.get('homePitcherHand', 'TBD'),
                    "season_era": home_pitcher_era
                }
            },
            "team_comparison": {
                 "lookback_games": lookback_games,
                 "away": away_summary,
                 "home": home_summary,
            },
        }
        return comparison_data

    except Exception as e:
        print(f"Unexpected error in get_game_comparison for game {game_id}: {e}")
        return {"error": f"Failed to generate comparison for game {game_id}: {e}"}