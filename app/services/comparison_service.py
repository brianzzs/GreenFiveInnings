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
            if position != 'N/A':
                 lineup.append({
                    "id": player_id,
                    "name": player_details.get('person', {}).get('fullName', 'Unknown'),
                    "position": position
                 })
        return lineup if lineup else None
    except Exception as e:
        print(f"Error extracting {team_key} lineup: {e}")
        return None

async def get_game_comparison(game_id: int, lookback_games: int = 10) -> Dict[str, Any]:
    """
    Generates a comparison between two teams for a specific game, 
    including lineups and focusing on relevant team stats based on the last N games.
    Args:
        game_id: The MLB gamePk for the game.
        lookback_games: How many recent completed games to consider for team stats (default 10).

    Returns:
        A dictionary containing game info (with lineups, pitcher ERA), team comparison, and prediction insights.
    """
    try:
        # 1. Fetch Full Game Data (needed for lineups, pitchers, etc.)
        raw_game_data = await mlb_stats_client.get_game_data_async(game_id)
        if not raw_game_data or 'gameData' not in raw_game_data or 'liveData' not in raw_game_data:
            return {"error": f"Could not fetch complete data for game ID {game_id}"}

        game_data = raw_game_data.get('gameData', {})
        live_data = raw_game_data.get('liveData', {})
        boxscore_data = live_data.get('boxscore', {})

        # 2. Extract Basic Game Info & Team Records
        teams_info = game_data.get('teams', {})
        away_team_info = teams_info.get('away', {})
        home_team_info = teams_info.get('home', {})
        datetime_info = game_data.get('datetime', {})
        venue_info = game_data.get('venue', {})
        status_info = game_data.get('status', {})

        away_team_id = away_team_info.get('id')
        home_team_id = home_team_info.get('id')
        
        if not away_team_id or not home_team_id:
            return {"error": f"Missing team ID(s) in game data for game {game_id}"}
        
        away_record_data = away_team_info.get('leagueRecord', {})
        home_record_data = home_team_info.get('leagueRecord', {})
        away_record_str = f"{away_record_data.get('wins', 0)}-{away_record_data.get('losses', 0)}"
        home_record_str = f"{home_record_data.get('wins', 0)}-{home_record_data.get('losses', 0)}"

        pitcher_details = player_service.fetch_and_cache_pitcher_info(game_id, raw_game_data)
        away_pitcher_id = pitcher_details.get('awayPitcherID')
        home_pitcher_id = pitcher_details.get('homePitcherID')
        current_year = str(datetime.datetime.now().year)

        away_lineup = _extract_lineup(boxscore_data, 'away')
        home_lineup = _extract_lineup(boxscore_data, 'home')

        away_summary_task = game_service.get_team_stats_summary(away_team_id, lookback_games)
        home_summary_task = game_service.get_team_stats_summary(home_team_id, lookback_games)
        
        away_pitcher_era_task = None
        if away_pitcher_id and away_pitcher_id != "TBD":
            away_pitcher_era_task = asyncio.to_thread(player_service.get_player_stats, away_pitcher_id, current_year)

        home_pitcher_era_task = None
        if home_pitcher_id and home_pitcher_id != "TBD":
            home_pitcher_era_task = asyncio.to_thread(player_service.get_player_stats, home_pitcher_id, current_year)

        results = await asyncio.gather(
            away_summary_task,
            home_summary_task,
            away_pitcher_era_task, 
            home_pitcher_era_task, 
            return_exceptions=True
        )

        away_summary = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0]), "games_analyzed": 0}
        home_summary = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1]), "games_analyzed": 0}
        away_pitcher_data = results[2] if results[2] and not isinstance(results[2], Exception) else {"error": str(results[2]) if isinstance(results[2], Exception) else "No data or TBD"}
        home_pitcher_data = results[3] if results[3] and not isinstance(results[3], Exception) else {"error": str(results[3]) if isinstance(results[3], Exception) else "No data or TBD"}

        def get_era_from_data(p_data):
            if not p_data or "error" in p_data:
                return "N/A"
            if "pitching_stats" in p_data: 
                 return p_data.get("pitching_stats", {}).get("season", {}).get("era", "N/A")
            elif "season_stats" in p_data: 
                if "era" in p_data["season_stats"]:
                     return p_data.get("season_stats", {}).get("era", "N/A")
            return "N/A" 

        away_pitcher_era = get_era_from_data(away_pitcher_data)
        home_pitcher_era = get_era_from_data(home_pitcher_data)
        
        if "error" in away_summary: print(f"Error fetching away team summary: {away_summary['error']}")
        if "error" in home_summary: print(f"Error fetching home team summary: {home_summary['error']}")

        comparison_data = {
            "game_info": {
                "game_id": game_id,
                "game_datetime": datetime_info.get('dateTime'),
                "status": status_info.get('abstractGameState', 'Unknown'),
                "venue": venue_info.get('name', 'TBD'),
                "away_team": {
                    "id": away_team_id,
                    "name": TEAM_NAMES.get(away_team_id, away_team_info.get('name', 'TBD')),
                    "record": away_record_str,
                    "lineup": away_lineup
                },
                "home_team": {
                    "id": home_team_id,
                    "name": TEAM_NAMES.get(home_team_id, home_team_info.get('name', 'TBD')),
                    "record": home_record_str,
                     "lineup": home_lineup
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
                "away": {
                    "games_analyzed": away_summary.get("games_analyzed", 0),
                    "nrfi": away_summary.get("nrfi"),
                    "game_nrfi_percentage": away_summary.get("game_nrfi_percentage"),
                    "win_percentage_f5": away_summary.get("win_percentage_f5"),
                    "over1_5F5": away_summary.get("over1_5F5"),
                    "over2_5F5": away_summary.get("over2_5F5")
                } if "error" not in away_summary else away_summary,
                "home": {
                    "games_analyzed": home_summary.get("games_analyzed", 0),
                    "nrfi": home_summary.get("nrfi"),
                    "game_nrfi_percentage": home_summary.get("game_nrfi_percentage"),
                    "win_percentage_f5": home_summary.get("win_percentage_f5"),
                    "over1_5F5": home_summary.get("over1_5F5"),
                    "over2_5F5": home_summary.get("over2_5F5")
                } if "error" not in home_summary else home_summary
            },
        }
        return comparison_data

    except Exception as e:
        print(f"Error generating game comparison for game ID {game_id}: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"An unexpected error occurred while generating comparison: {str(e)}"} 