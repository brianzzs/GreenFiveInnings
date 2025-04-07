from typing import Dict, List, Optional
import datetime
import pytz

def convert_utc_to_local(utc_datetime_str: str, target_tz: str = 'America/New_York') -> str:
    """Converts a UTC datetime string to a specified timezone."""
    try:
        utc_dt = datetime.datetime.strptime(utc_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
        utc_dt = pytz.UTC.localize(utc_dt)
        local_tz_obj = pytz.timezone(target_tz)
        local_dt = utc_dt.astimezone(local_tz_obj)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    except (ValueError, TypeError) as e:
        print(f"Error converting UTC time '{utc_datetime_str}': {e}")
        return utc_datetime_str 
    except pytz.UnknownTimeZoneError:
        print(f"Unknown timezone: {target_tz}. Falling back to UTC.")
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S %Z%z") 


def extract_lineup(boxscore_data: Dict, team_key: str) -> Optional[List[Dict]]:
    """Helper function to extract and format batting order from boxscore data."""
    if not boxscore_data or team_key not in ['home', 'away']:
        print(f"[extract_lineup] Invalid input: boxscore_data={boxscore_data}, team_key={team_key}")
        return None
    try:
        team_data = boxscore_data.get('teams', {}).get(team_key, {})
        player_info = team_data.get('players', {})
        batting_order_ids = team_data.get('battingOrder', [])
        
        if not batting_order_ids:
            print(f"[extract_lineup] No batting order found for {team_key} team.")
            return None 

        lineup = []
        for player_id in batting_order_ids:
            player_key = f'ID{player_id}'
            player_details = player_info.get(player_key, {})
            if not player_details: 
                print(f"[extract_lineup] Warning: Missing player details for ID {player_id} in {team_key} lineup.")
                continue 
                
            position = player_details.get('position', {}).get('abbreviation', 'N/A')
            if position == 'P': 
                continue
                
            batting_avg = player_details.get('seasonStats', {}).get('batting', {}).get('avg', 'N/A')
            
            lineup.append({
                "id": player_id,
                "name": player_details.get('person', {}).get('fullName', 'Unknown'),
                "position": position,
                "avg": batting_avg,
            })
            
        return lineup if lineup else None
    except Exception as e:
        print(f"[extract_lineup] Error extracting {team_key} lineup: {e}")
        return None 