import statsapi
import asyncio
from typing import Dict, List, Any, Optional
import requests

def get_game_data(game_pk: int) -> Dict[str, Any]:
    """Fetches raw game data using statsapi.get."""
    try:
        return statsapi.get("game", {"gamePk": game_pk})
    except Exception as e:
        print(f"Error fetching game data for gamePk {game_pk}: {e}")
        raise

def get_player_stats(
    player_id: int, group: str, type: str, season: Optional[str] = None
) -> str: 
    """Fetches player stats using statsapi.player_stats."""
    params = {"personId": player_id, "group": group, "type": type}
    if season:
        params["season"] = season
    try:
        return statsapi.player_stats(**params) 
    except Exception as e:
        print(f"Error fetching player stats for player {player_id}: {e}")
        raise

def lookup_player(query: str) -> List[Dict[str, Any]]:
    """Looks up a player by name using statsapi.lookup_player."""
    try:
        return statsapi.lookup_player(query)
    except Exception as e:
        print(f"Error looking up player with query '{query}': {e}")
        raise

def get_schedule(
    start_date: str, end_date: Optional[str] = None, team_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetches schedule using statsapi.schedule."""
    params = {"start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    if team_id:
        params["team"] = team_id
    try:
        return statsapi.schedule(**params)
    except Exception as e:
        print(f"Error fetching schedule with params {params}: {e}")
        raise

def get_player_info_with_stats(player_id: int, season: str) -> Dict[str, Any]:
    """Fetches player info hydrated with season stats using a direct API call."""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group=[hitting,pitching],type=[season],season={season})"
    try:
        response = requests.get(url)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching player info/stats for player {player_id}, season {season}: {e}")
        raise 

def get_player_stat_data(player_id: int, group: str, type: str) -> Dict[str, Any]:
    """Fetches player stat data using statsapi.player_stat_data."""
    params = {"personId": player_id, "group": group, "type": type}
    try:
        return statsapi.player_stat_data(**params)
    except Exception as e:
        print(f"Error fetching player stat data for player {player_id}, group {group}, type {type}: {e}")
        raise

def get_standings(league_id: str = "103,104", date: Optional[str] = None) -> Dict:
    """Fetches standings data using statsapi.standings_data."""
    params = {"leagueId": league_id}
    if date:
        params["date"] = date
    try:
        return statsapi.standings_data(**params)
    except Exception as e:
        print(f"Error fetching standings data with params {params}: {e}")
        raise

async def get_schedule_async(
    start_date: str, end_date: Optional[str] = None, team_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetches schedule asynchronously using asyncio.to_thread."""
    # Filtering is currently done in schedule_service.py
    return await asyncio.to_thread(get_schedule, start_date, end_date, team_id)

async def get_game_data_async(game_pk: int) -> Dict[str, Any]:
    """Fetches raw game data asynchronously using asyncio.to_thread."""
    return await asyncio.to_thread(get_game_data, game_pk) 