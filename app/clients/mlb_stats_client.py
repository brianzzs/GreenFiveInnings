import statsapi
import asyncio
from typing import Dict, List, Any, Optional
import requests
from async_lru import alru_cache
from functools import lru_cache

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

@lru_cache(maxsize=512)
def get_player_h2h_stats(batter_id: int, pitcher_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetches and extracts relevant *career total* H2H stats for a batter vs a pitcher.

    Args:
        batter_id: The MLBAM ID of the batter.
        pitcher_id: The MLBAM ID of the pitcher.

    Returns:
        A dictionary with relevant H2H stats (PA, AB, H, HR, RBI, BB, SO, AVG, OBP, SLG, OPS)
        or None if no H2H data is found or an error occurs.
        Returns a dict like {"PA": 0} if the API call succeeds but there's no history.
    """
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsTeamTotal&group=hitting&opposingPlayerId={pitcher_id}&language=en"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

        stats_list = data.get("stats", [])
        if not stats_list:
            return {"PA": 0} 

        total_stats_data = None
        for stat_entry in stats_list:
            stat_type = stat_entry.get("type", {})
            if stat_type and stat_type.get("displayName") == "vsTeamTotal":
                total_stats_data = stat_entry
                break

        if not total_stats_data:
            return {"PA": 0} 

        splits = total_stats_data.get("splits", [])
        if not splits:
            return {"PA": 0}

        raw_stats = splits[0].get("stat", {})
        if not raw_stats or raw_stats.get("plateAppearances", 0) == 0:
             return {"PA": 0}
        relevant_stats = {
            "PA": raw_stats.get("plateAppearances"),
            "AB": raw_stats.get("atBats"),
            "H": raw_stats.get("hits"),
            "2B": raw_stats.get("doubles"),
            "3B": raw_stats.get("triples"),
            "HR": raw_stats.get("homeRuns"),
            "RBI": raw_stats.get("rbi"),
            "BB": raw_stats.get("baseOnBalls"),
            "SO": raw_stats.get("strikeOuts"),
            "AVG": raw_stats.get("avg"),
            "OBP": raw_stats.get("obp"),
            "SLG": raw_stats.get("slg"),
            "OPS": raw_stats.get("ops"),
        }
        return relevant_stats

    except requests.exceptions.Timeout:
        print(f"Timeout fetching H2H stats for batter {batter_id} vs pitcher {pitcher_id}")
        return None 
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        print(f"Error fetching H2H stats for batter {batter_id} vs pitcher {pitcher_id} (Status: {status_code}): {e}")
        if status_code == 404: 
             return {"error": "Not Found"}
        return None 
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        print(f"Error parsing H2H JSON for batter {batter_id} vs pitcher {pitcher_id}: {e}")
        return None 


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

@alru_cache(maxsize=128)
async def get_game_data_async(game_pk: int) -> Dict[str, Any]:
    """Fetches raw game data asynchronously using asyncio.to_thread."""
    return await asyncio.to_thread(get_game_data, game_pk) 