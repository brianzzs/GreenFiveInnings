import statsapi
from typing import List, Dict, Union, Optional
from calculations import TEAM_NAMES
def search_player_by_name(name: str) -> List[Dict[str, Union[str, int]]]:
    """
    Search for players by name and return a list of matching players with their IDs
    """
    try:
        players = statsapi.lookup_player(name)
        
        return [
            {
                "id": player['id'],
                "full_name": player['fullName'],
                "first_name": player['firstName'],
                "last_name": player['lastName'],
                "current_team": player.get('currentTeam', {}).get('name', 'Not Available'),
                "position": player.get('primaryPosition', {}).get('abbreviation', 'N/A'),
                "active": player.get('active', False)
            }
            for player in players
        ]
    except Exception as e:
        print(f"Error searching for player: {e}")
        return []

def get_player_stats(player_id: int) -> Dict[str, Union[str, Dict]]:
    try:
        player_info = statsapi.lookup_player(player_id)[0]
        player_batting_data = statsapi.player_stat_data(player_id, "hitting", "season")
        
        # Get regular stats
        stats = statsapi.player_stats(player_id, "season")
        career_stats = statsapi.player_stats(player_id, "career")
        
        # Get split stats
        split_stats = statsapi.player_stats(player_id, "season", "vsRHP") 
        split_stats_left = statsapi.player_stats(player_id, "season", "vsLHP") 
        
        is_pitcher = player_info.get('primaryPosition', {}).get('abbreviation') == 'P'
        
        # Construct MLB content API image URLs
        image_urls = {
            "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current",
            "action": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:action:hero:current.png/w_2208,q_auto:good/v1/people/{player_id}/action/hero/current"
        } 
        
        return {
            "player_info": {
                "id": player_info['id'],
                "full_name": player_info['fullName'],
                "current_team": TEAM_NAMES.get(player_info.get('currentTeam', {}).get('id', 'Not Available'), 'Not Available'),
                "position": player_info.get('primaryPosition', {}).get('abbreviation', 'N/A'),
                "active": player_info.get('active', False),
                "bat_side": player_batting_data.get('bat_side', {})[:1],
                "throw_hand": player_batting_data.get('pitch_hand', {})[:1],
                "images": image_urls
            },
            "season_stats": parse_stats(stats, is_pitcher),
            "career_stats": parse_stats(career_stats, is_pitcher),
            "split_stats": {
                "vs_right": parse_split_stats(split_stats),
                "vs_left": parse_split_stats(split_stats_left)
            }
        }
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {"error": "Player not found or error fetching stats"}

def parse_stats(stats_string: str, is_pitcher: bool) -> Dict[str, str]:
    if not stats_string:
        return {}
        
    stats_dict = {}
    for line in stats_string.split('\n'):
        if ': ' in line:
            key, value = line.split(': ')
            stats_dict[key.lower()] = value
    
    if is_pitcher:
        return {
            "era": stats_dict.get("era", "N/A"),
            "games": stats_dict.get("games", "N/A"),
            "games_started": stats_dict.get("gamesstarted", "N/A"),
            "innings_pitched": stats_dict.get("inningspitched", "N/A"),
            "wins": stats_dict.get("wins", "N/A"),
            "losses": stats_dict.get("losses", "N/A"),
            "saves": stats_dict.get("saves", "N/A"),
            "strikeouts": stats_dict.get("strikeouts", "N/A"),
            "whip": stats_dict.get("whip", "N/A"),
            "walks": stats_dict.get("walks", "N/A")
        }
    else:
        return {
            "avg": stats_dict.get("avg", "N/A"),
            "games": stats_dict.get("games", "N/A"),
            "at_bats": stats_dict.get("atbats", "N/A"),
            "runs": stats_dict.get("runs", "N/A"),
            "hits": stats_dict.get("hits", "N/A"),
            "home_runs": stats_dict.get("homeruns", "N/A"),
            "rbi": stats_dict.get("rbi", "N/A"),
            "stolen_bases": stats_dict.get("stolenbases", "N/A"),
            "obp": stats_dict.get("obp", "N/A"),
            "slg": stats_dict.get("slg", "N/A")
        }

def parse_split_stats(stats_string: str) -> Dict[str, str]:
    """Parse split statistics (vs LHP/RHP)"""
    if not stats_string:
        return {}
        
    stats_dict = {}
    for line in stats_string.split('\n'):
        if ': ' in line:
            key, value = line.split(': ')
            stats_dict[key.lower()] = value
    
    return {
        "avg": stats_dict.get("avg", "N/A"),
        "at_bats": stats_dict.get("atbats", "N/A"),
        "hits": stats_dict.get("hits", "N/A"),
        "home_runs": stats_dict.get("homeruns", "N/A"),
        "obp": stats_dict.get("obp", "N/A"),
        "slg": stats_dict.get("slg", "N/A"),
        "ops": stats_dict.get("ops", "N/A")
    } 