import asyncio
import datetime
from typing import Dict, Any, List, Optional
from app.services import game_service, player_service, schedule_service
from app.clients import mlb_stats_client
from app.utils.calculations import TEAM_NAMES

def _extract_lineup(boxscore_data: Dict, team_key: str) -> Optional[List[Dict]]:
    """Helper function to extract and format batting order from boxscore data."""
    try:
        team_data = boxscore_data.get('teams', {}).get(team_key, {})
        player_info = team_data.get('players', {})
        batting_order_ids = team_data.get('battingOrder', [])
        
        if not batting_order_ids:
            return None 

        lineup = []
        for player_id in batting_order_ids:
            player_key = f'ID{player_id}'
            player_details = player_info.get(player_key, {})
            position = player_details.get('position', {}).get('abbreviation', 'N/A')
            batting_avg = player_details.get('seasonStats', {}).get('batting', {}).get('avg', 'N/A')
            if position != 'N/A':
                 lineup.append({
                    "id": player_id,
                    "name": player_details.get('person', {}).get('fullName', 'Unknown'),
                    "position": position,
                    "avg": batting_avg,
                 })
        return lineup if lineup else None
    except Exception as e:
        print(f"Error extracting {team_key} lineup: {e}")
        return None

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


        away_lineup = _extract_lineup(boxscore_data, 'away') 
        home_lineup = _extract_lineup(boxscore_data, 'home') 

        tasks_to_run = []

        tasks_to_run.append(game_service.get_team_stats_summary(away_team_id, lookback_games))
        tasks_to_run.append(game_service.get_team_stats_summary(home_team_id, lookback_games))

        away_pitcher_task_index = -1
        if away_pitcher_id and away_pitcher_id != "TBD":
            tasks_to_run.append(asyncio.to_thread(player_service.get_player_stats, away_pitcher_id, current_year))
            away_pitcher_task_index = len(tasks_to_run) - 1
        else:
             tasks_to_run.append(asyncio.sleep(0, result={"error": "TBD/Missing ID"})) 

        home_pitcher_task_index = -1
        if home_pitcher_id and home_pitcher_id != "TBD":
            tasks_to_run.append(asyncio.to_thread(player_service.get_player_stats, home_pitcher_id, current_year))
            home_pitcher_task_index = len(tasks_to_run) - 1
        else:
             tasks_to_run.append(asyncio.sleep(0, result={"error": "TBD/Missing ID"})) 


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

        away_pitcher_data = results[away_pitcher_task_index] if away_pitcher_task_index != -1 and not isinstance(results[away_pitcher_task_index], Exception) else {"error": "TBD/Missing ID or Fetch Error"}
        home_pitcher_data = results[home_pitcher_task_index] if home_pitcher_task_index != -1 and not isinstance(results[home_pitcher_task_index], Exception) else {"error": "TBD/Missing ID or Fetch Error"}

        # Helper to safely get ERA
        def get_era_from_data(p_data):
            # ...(your existing get_era_from_data function)...
            if not p_data or isinstance(p_data, Exception) or "error" in p_data:
                 return "N/A"
            stats = p_data.get("pitching_stats", {}).get("season", {}) or \
                    p_data.get("season_stats", {})
            return stats.get("era", "N/A")

        away_pitcher_era = get_era_from_data(away_pitcher_data)
        home_pitcher_era = get_era_from_data(home_pitcher_data)

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
                    "lineup": away_lineup_with_h2h
                },
                "home_team": {
                    "id": home_team_id,
                    "name": TEAM_NAMES.get(home_team_id, home_team_info.get('name', 'TBD')),
                    "record": home_record_str,
                    "lineup": home_lineup_with_h2h
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