import statsapi
import requests
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
                "current_team": player.get('team', {}).get('name', 'Not Available'),
                "position": player.get('primaryPosition', {}).get('abbreviation', 'N/A'),
            }
            for player in players
        ]
    except Exception as e:
        print(f"Error searching for player: {e}")
        return []

def get_player_stats(player_id: int, season: str) -> Dict[str, Union[str, Dict]]:
    try:
        # Direct API call to get player data with stats for specific season 
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group=[hitting,pitching],type=[season],season={season})"
        response = requests.get(url)
        data = response.json()
        
        if not data.get('people'):
            return {"error": "Player not found"}
            
        player_info = data['people'][0]
        is_pitcher = player_info.get('primaryPosition', {}).get('abbreviation') == 'P'
        
        # Get career stats based on player type
        if is_pitcher:
            career_stats = statsapi.player_stat_data(player_id, "pitching", "career")
        else:
            career_stats = statsapi.player_stat_data(player_id, "hitting", "career")
        
        # Get season stats from the response
        stats_data = player_info.get('stats', [])
        hitting_stats = stats_data[0]['splits'][0]['stat']
        pitching_stats = stats_data[0]['splits'][0]['stat']


        career_stats = career_stats.get("stats", [])[0].get("stats")
        
        for stat in stats_data:
            if stat.get('group', {}).get('displayName') == 'hitting':
                if stat.get('splits'):
                    hitting_stats = stat['splits'][0]['stat']
            elif stat.get('group', {}).get('displayName') == 'pitching':
                if stat.get('splits'):
                    pitching_stats = stat['splits'][0]['stat']
        
        # Construct image URLs
        image_urls = {
            "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current",
            "action": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:action:hero:current.png/w_2208,q_auto:good/v1/people/{player_id}/action/hero/current"
        }
        
        return {
            "player_info": {
                "id": player_info['id'],
                "full_name": player_info['fullName'],
                "current_team": TEAM_NAMES.get(player_info.get('stats', {})[0].get('splits', {})[0].get('team', {}).get('id'), 'Not Available'),
                "position": player_info.get('primaryPosition', {}).get('abbreviation', 'N/A'),
                "bat_side": player_info.get('batSide', {}).get('code', 'N/A'),
                "throw_hand": player_info.get('pitchHand', {}).get('code', 'N/A'),
                "birth_date": player_info.get('birthDate'),
                "age": player_info.get('currentAge'),
                "images": image_urls
            },
            "season": season,
            "season_stats": format_stats(hitting_stats if not is_pitcher else pitching_stats, is_pitcher),
            "career_stats": format_stats(career_stats, is_pitcher)
        }
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {"error": f"Error fetching player stats: {str(e)}"}

def format_stats(stats: Dict, is_pitcher: bool) -> Dict[str, str]:
    if not stats:
        return {}
        
    if is_pitcher:
        return {
            "era": str(stats.get('era', 'N/A')),
            "games": str(stats.get('gamesPlayed', 'N/A')),
            "games_started": str(stats.get('gamesStarted', 'N/A')),
            "innings_pitched": str(stats.get('inningsPitched', 'N/A')),
            "wins": str(stats.get('wins', 'N/A')),
            "losses": str(stats.get('losses', 'N/A')),
            "saves": str(stats.get('saves', 'N/A')),
            "strikeouts": str(stats.get('strikeOuts', 'N/A')),
            "whip": str(stats.get('whip', 'N/A')),
            "walks": str(stats.get('baseOnBalls', 'N/A'))
        }
    else:
        return {
            "avg": str(stats.get('avg', 'N/A')),
            "games": str(stats.get('gamesPlayed', 'N/A')),
            "at_bats": str(stats.get('atBats', 'N/A')),
            "runs": str(stats.get('runs', 'N/A')),
            "hits": str(stats.get('hits', 'N/A')),
            "home_runs": str(stats.get('homeRuns', 'N/A')),
            "rbi": str(stats.get('rbi', 'N/A')),
            "stolen_bases": str(stats.get('stolenBases', 'N/A')),
            "obp": str(stats.get('obp', 'N/A')),
            "slg": str(stats.get('slg', 'N/A')),
            "ops": str(stats.get('ops', 'N/A'))
        }
