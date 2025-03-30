from functools import lru_cache
from typing import Dict, Any, List, Union, Optional
from app.clients import mlb_stats_client
from app.utils.calculations import TEAM_NAMES 
import datetime
import asyncio

@lru_cache(maxsize=128) 
def parse_stats(stats_string: str) -> dict:
    """Parses the stats string returned by the MLB API."""
    if not stats_string:
        return {
            "wins": "TBD",
            "losses": "TBD",
            "era": "TBD"
        }
        
    try:
        lines = stats_string.replace('\r\n', '\n').split("\n")
        stats = {}
        for line in lines:
            if ": " in line:
                key_val = line.split(": ", 1)
                if len(key_val) == 2:
                    key, value = key_val
                    stats[key.strip().lower().replace(' ', '_')] = value.strip()
                    
        return {
            "wins": stats.get("wins", "TBD"),
            "losses": stats.get("losses", "TBD"),
            "era": stats.get("era", "TBD")
        }
    except Exception as e:
        print(f"Error parsing stats string: {stats_string}. Error: {e}")
        return {
            "wins": "TBD",
            "losses": "TBD",
            "era": "TBD"
        }

def fetch_and_cache_pitcher_info(game_id: int, game_data: Dict = None) -> Dict:
    """Fetches and processes probable pitcher info for a game."""
    try:
        if not game_data:
            game_data = mlb_stats_client.get_game_data(game_pk=game_id)

        data_root = game_data.get("gameData", {})
        probable_pitchers_data = data_root.get("probablePitchers", {})
        players_data = data_root.get("players", {})

        home_pitcher = probable_pitchers_data.get("home", {"fullName": "TBD", "id": "TBD"})
        away_pitcher = probable_pitchers_data.get("away", {"fullName": "TBD", "id": "TBD"})

        def get_pitcher_hand(pitcher_id):
            player_key = f'ID{pitcher_id}'
            player_details = players_data.get(player_key, {})
            pitch_hand = player_details.get("pitchHand", {})
            return pitch_hand.get("code", "TBD")

        home_pitcher_hand = get_pitcher_hand(home_pitcher.get("id"))
        away_pitcher_hand = get_pitcher_hand(away_pitcher.get("id"))

        def get_pitcher_stats(pitcher_id):
            if pitcher_id == "TBD" or not pitcher_id:
                return {"wins": "TBD", "losses": "TBD", "era": "TBD"}
            try:
                stats_str = mlb_stats_client.get_player_stats(
                    player_id=pitcher_id, group="pitching", type="season"
                )
                return parse_stats(stats_str)
            except Exception as e:
                print(f"Failed to get/parse stats for pitcher {pitcher_id}: {e}")
                return {"wins": "TBD", "losses": "TBD", "era": "TBD"}

        home_pitcher_stats = get_pitcher_stats(home_pitcher.get("id"))
        away_pitcher_stats = get_pitcher_stats(away_pitcher.get("id"))

        return {
            "homePitcherID": home_pitcher.get("id", "TBD"),
            "homePitcher": home_pitcher.get("fullName", "TBD"),
            "homePitcherHand": home_pitcher_hand,
            "homePitcherWins": home_pitcher_stats["wins"],
            "homePitcherLosses": home_pitcher_stats["losses"],
            "homePitcherERA": home_pitcher_stats["era"],
            "awayPitcherID": away_pitcher.get("id", "TBD"),
            "awayPitcher": away_pitcher.get("fullName", "TBD"),
            "awayPitcherHand": away_pitcher_hand,
            "awayPitcherWins": away_pitcher_stats["wins"],
            "awayPitcherLosses": away_pitcher_stats["losses"],
            "awayPitcherERA": away_pitcher_stats["era"],
        }
    except Exception as e:
        print(f"Error fetching pitcher info for game {game_id}: {e}")
        return {
            "homePitcherID": "TBD", "homePitcher": "TBD", "homePitcherHand": "TBD",
            "homePitcherWins": "TBD", "homePitcherLosses": "TBD", "homePitcherERA": "TBD",
            "awayPitcherID": "TBD", "awayPitcher": "TBD", "awayPitcherHand": "TBD",
            "awayPitcherWins": "TBD", "awayPitcherLosses": "TBD", "awayPitcherERA": "TBD",
        }


def search_player_by_name(name: str) -> List[Dict[str, Union[str, int]]]:
    """
    Search for players by name and return a list of matching players with their IDs
    """
    try:
        players = mlb_stats_client.lookup_player(name)

        
        return [
            {
                "id": player['id'],
                "full_name": player['fullName'],
                "first_name": player['firstName'],
                "last_name": player['lastName'],
                "current_team": TEAM_NAMES.get(player['currentTeam']['id'], 'Not Available'),
                "image_url": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player['id']}/headshot/67/current",
                "position": player.get('primaryPosition', {}).get('abbreviation', 'N/A'),
            }
            for player in players
        ]
    except Exception as e:
        print(f"Error searching for player: {e}")
        return []

@lru_cache(maxsize=128)
def get_player_stats(player_id: int, season: str) -> Dict[str, Union[str, Dict]]:
    try:
        print(f"[get_player_stats] Looking up player ID: {player_id}")
        lookup_result = mlb_stats_client.lookup_player(str(player_id))
        if not lookup_result:
             return {"error": f"Could not look up player ID {player_id}"}
        basic_player_info = lookup_result[0] 
        current_team_id = basic_player_info.get('currentTeam', {}).get('id')
        print(f"[get_player_stats] Current team ID from lookup: {current_team_id}")
        current_team_name = TEAM_NAMES.get(current_team_id, 'Not Available')

        data = mlb_stats_client.get_player_info_with_stats(player_id, season)
        
        if not data.get('people'):
             print(f"[get_player_stats] Player {player_id} found via lookup, but no stats data returned for season {season}. Returning basic info.")
             return {
                 "player_info": {
                     "id": basic_player_info.get('id'),
                     "full_name": basic_player_info.get('fullName'),
                     "current_team": current_team_name, # Use name from lookup
                     "position": basic_player_info.get('primaryPosition', {}).get('abbreviation', 'N/A'),
                 },
                 "season": season,
                 "season_stats": {},
                 "career_stats": {}
             }
            
        player_info = data['people'][0] # Use this for stats primarily now
        position = player_info.get('primaryPosition', {}).get('abbreviation', 'N/A')
        is_pitcher = position == 'P'
        is_two_way = position == 'TWP'
        
        hitting_career = mlb_stats_client.get_player_stat_data(player_id, "hitting", "career")
        pitching_career = mlb_stats_client.get_player_stat_data(player_id, "pitching", "career") if (is_pitcher or is_two_way) else None
        
        stats_data = player_info.get('stats', [])
        hitting_stats = {}
        pitching_stats = {}

        print(f"[get_player_stats] Raw stats_data for player {player_id}: {stats_data}") 

        for stat in stats_data:
            group = stat.get('group', {}).get('displayName')
            splits = stat.get('splits', [])
            if splits: 
                split_stat = splits[0].get('stat', {})
                if group == 'hitting':
                    hitting_stats = split_stat
                elif group == 'pitching':
                    pitching_stats = split_stat

        hitting_career_stats = {}
        if hitting_career:
            career_stats_list = hitting_career.get("stats", [])
            if career_stats_list:
                 hitting_career_stats = career_stats_list[0].get("stats", {}) 

        pitching_career_stats = {}
        if pitching_career:
             career_stats_list = pitching_career.get("stats", [])
             if career_stats_list:
                  pitching_career_stats = career_stats_list[0].get("stats", {})
        
        image_urls = {
            "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current",
            "action": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:action:hero:current.png/w_2208,q_auto:good/v1/people/{player_id}/action/hero/current"
        }
        
        response_data = {
            "player_info": {
                "id": player_info.get('id'), # Use stats response if available, fallback? maybe basic_info is better
                "full_name": player_info.get('fullName'),
                "current_team": current_team_name, # Use name from lookup result
                "position": position,
                "bat_side": player_info.get('batSide', {}).get('code', 'N/A'),
                "throw_hand": player_info.get('pitchHand', {}).get('code', 'N/A'),
                "birth_date": player_info.get('birthDate'),
                "age": player_info.get('currentAge'),
                "images": image_urls
            },
            "season": season
        }
        
        if is_two_way:
            response_data.update({
                "hitting_stats": {
                    "season": format_stats(hitting_stats, False),
                    "career": format_stats(hitting_career_stats, False)
                },
                "pitching_stats": {
                    "season": format_stats(pitching_stats, True),
                    "career": format_stats(pitching_career_stats, True)
                }
            })
        else:
            response_data.update({
                "season_stats": format_stats(hitting_stats if not is_pitcher else pitching_stats, is_pitcher),
                "career_stats": format_stats(hitting_career_stats if not is_pitcher else pitching_career_stats, is_pitcher)
            })
        
        return response_data
        
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
            "earned_runs": str(stats.get('earnedRuns', 'N/A')),
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

async def get_player_recent_stats(player_id: int, num_games: int) -> Dict[str, Union[str, List[Dict[str, Union[str, int]]]]]:
    """
    Get recent game stats for a player
    Don't use lru_cache on async functions - they don't work together
    """
    try:
        player_lookup_result = mlb_stats_client.lookup_player(str(player_id))
        if not player_lookup_result:
             return {"error": f"Could not look up player ID {player_id}"}
        player_info = player_lookup_result[0]

        team_id = player_info.get('currentTeam', {}).get('id')
        position = player_info.get('primaryPosition', {}).get('abbreviation', 'N/A')
        is_pitcher = position == 'P'
        
        if not team_id:
            return {"error": "Team ID not found for player"}
        
        end_date = datetime.date.today()
        player_stats = []
        days_to_search = 30  
        seen_dates = set()  # Track dates we've already processed
        
        while len(player_stats) < num_games and days_to_search <= 180:
            start_date = end_date - datetime.timedelta(days=days_to_search)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            recent_games = await mlb_stats_client.get_schedule_async(
                team_id=team_id,
                start_date=start_date_str,
                end_date=end_date_str
            )
            
            # Filter completed games and sort by date in descending order
            recent_game_ids = [game['game_id'] for game in sorted(
                [game for game in recent_games if game['status'] == 'Final'],
                key=lambda x: x['game_datetime'],
                reverse=True
            )]
            
            tasks = [mlb_stats_client.get_game_data_async(game_id) for game_id in recent_game_ids]
            game_data_list = await asyncio.gather(*tasks)
            
            game_data_list.sort(
                key=lambda x: x['gameData']['datetime']['dateTime'],
                reverse=True
            )
            
            for game_data in game_data_list:
                if len(player_stats) >= num_games:
                    break
                    
                live_data = game_data.get('liveData', {})
                boxscore = live_data.get('boxscore', {})
                teams = boxscore.get('teams', {})
                home_team = teams.get('home', {})
                away_team = teams.get('away', {})
                players = home_team.get('players', {})
                players.update(away_team.get('players', {}))
                
                player_key = f'ID{player_id}'
                if player_key in players:
                    game_date = game_data['gameData']['datetime']['dateTime']
                    date_only = game_date.split('T')[0]
                    
                    # Skip if we've already seen this date
                    if date_only in seen_dates:
                        continue
                        
                    seen_dates.add(date_only)
                    
                    if is_pitcher:
                        player_game_stats = players[player_key].get('stats', {}).get('pitching', {})
                        if player_game_stats.get('inningsPitched'):  # Only include games where they pitched
                            opponent_team = away_team if home_team['team']['id'] == team_id else home_team
                            player_stats.append({
                                "game_id": game_data['gameData']['game']['pk'],
                                "game_date": game_date,
                                "innings_pitched": player_game_stats.get('inningsPitched', 0),
                                "hits_allowed": player_game_stats.get('hits', 0),
                                "home_runs_allowed": player_game_stats.get('homeRuns', 0),
                                "walks_allowed": player_game_stats.get('baseOnBalls', 0),
                                "strikeouts": player_game_stats.get('strikeOuts', 0),
                                "runs": player_game_stats.get('runs', 0),
                                "opponent_team": TEAM_NAMES.get(opponent_team['team']['id'], 'Unknown')
                            })
                    else:
                        # For batters, check if they had any at-bats or plate appearances
                        player_game_stats = players[player_key].get('stats', {}).get('batting', {})
                        if player_game_stats.get('atBats') or player_game_stats.get('plateAppearances'):
                            opponent_team = away_team if home_team['team']['id'] == team_id else home_team
                            is_home_team = home_team['team']['id'] == team_id

                            try:
                                opponent_pitcher = game_data['gameData']['probablePitchers']['away' if is_home_team else 'home']['fullName']
                            except KeyError:
                                opponent_pitcher = "Unknown"

                            player_stats.append({
                                "game_id": game_data['gameData']['game']['pk'],
                                "game_date": game_date,
                                "hits": player_game_stats.get('hits', 0),
                                "runs": player_game_stats.get('runs', 0),
                                "rbis": player_game_stats.get('rbi', 0),
                                "home_runs": player_game_stats.get('homeRuns', 0),
                                "walks": player_game_stats.get('baseOnBalls', 0),
                                "at_bats": player_game_stats.get('atBats', 0),
                                "avg": round((player_game_stats.get("hits") / player_game_stats.get("atBats")) if player_game_stats.get("atBats") else 0, 3),
                                "strikeouts": player_game_stats.get('strikeOuts', 0),
                                "opponent_team": TEAM_NAMES.get(opponent_team['team']['id'], 'Unknown'),
                                "opponent_pitcher": opponent_pitcher
                            })
            
            # Increase search window if we haven't found enough games
            days_to_search *= 2
        
        player_stats.sort(key=lambda x: x['game_date'], reverse=True)
        player_stats = player_stats[:num_games]
        
        return {
            "player_id": player_id,
            "player_name": player_info['fullName'],
            "recent_stats": player_stats,
            "games_found": len(player_stats)
        }
        
    except Exception as e:
        print(f"Error fetching recent player stats: {e}")
        return {"error": f"Error fetching recent player stats: {str(e)}"}

def calculate_betting_stats(recent_stats: List[Dict], is_pitcher: bool) -> Dict[str, float]:
    """Calculate percentages for common betting markets based on recent game stats"""
    total_games = len(recent_stats)
    if total_games == 0:
        return {"error": "No games found"}
    
    betting_markets = {}
    
    if is_pitcher:
        # Pitcher betting markets
        innings_pitched_thresholds = [4.5, 5.5, 6.5]
        for threshold in innings_pitched_thresholds:
            games_over = sum(1 for game in recent_stats if float(game.get('innings_pitched', 0)) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_innings_pitched"] = round(games_over / total_games * 100, 2)
        
        hits_allowed_thresholds = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]
        for threshold in hits_allowed_thresholds:
            games_over = sum(1 for game in recent_stats if game.get('hits_allowed', 0) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_hits_allowed"] = round(games_over / total_games * 100, 2)
        
        runs_allowed_thresholds = [1.5, 2.5, 3.5, 4.5, 5.5]
        for threshold in runs_allowed_thresholds:
            if 'runs' in recent_stats[0]:
                games_over = sum(1 for game in recent_stats if game.get('runs', 0) > threshold)
            else:
                games_over = sum(1 for game in recent_stats if (game.get('hits_allowed', 0) + game.get('walks_allowed', 0)) / 3 > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_runs_allowed"] = round(games_over / total_games * 100, 2)
        
        # Strikeouts
        k_thresholds = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5]
        for threshold in k_thresholds:
            games_over = sum(1 for game in recent_stats if game.get('strikeouts', 0) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_strikeouts"] = round(games_over / total_games * 100, 2)
    
    else:
        # Batter betting markets
        hit_thresholds = [0.5, 1.5, 2.5]
        for threshold in hit_thresholds:
            games_over = sum(1 for game in recent_stats if game.get('hits', 0) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_hits"] = round(games_over / total_games * 100, 2)
        
        # Total bases (calculate from hits, doubles, triples, home runs)
        for game in recent_stats:
            # Calculate total bases if not present
            if 'total_bases' not in game:
                singles = game.get('hits', 0) - game.get('doubles', 0) - game.get('triples', 0) - game.get('home_runs', 0)
                game['total_bases'] = singles + 2 * game.get('doubles', 0) + 3 * game.get('triples', 0) + 4 * game.get('home_runs', 0)
                
                # If we only have hits and home runs
                if 'doubles' not in game and 'triples' not in game:
                    game['total_bases'] = game.get('hits', 0) + 3 * game.get('home_runs', 0)
        
        base_thresholds = [1.5, 2.5, 3.5]
        for threshold in base_thresholds:
            games_over = sum(1 for game in recent_stats if game.get('total_bases', 0) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_total_bases"] = round(games_over / total_games * 100, 2)
        
        # Home runs
        hr_threshold = 0.5
        games_over = sum(1 for game in recent_stats if game.get('home_runs', 0) > hr_threshold)
        betting_markets[f"over_{str(hr_threshold).replace('.', '_')}_home_runs"] = round(games_over / total_games * 100, 2)
        
        # RBIs
        rbi_thresholds = [0.5, 1.5, 2.5]
        for threshold in rbi_thresholds:
            games_over = sum(1 for game in recent_stats if game.get('rbis', 0) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_rbis"] = round(games_over / total_games * 100, 2)
        
        # Hits + Runs + RBIs combined
        hr_rbi_thresholds = [1.5, 2.5, 3.5, 4.5]
        for threshold in hr_rbi_thresholds:
            games_over = sum(1 for game in recent_stats if (game.get('hits', 0) + game.get('runs', 0) + game.get('rbis', 0)) > threshold)
            betting_markets[f"over_{str(threshold).replace('.', '_')}_hits_runs_rbis"] = round(games_over / total_games * 100, 2)
    
    return betting_markets

async def get_player_betting_stats(player_id: int, num_games: int) -> Dict[str, Union[str, Dict]]:
    """Get player stats with betting market analysis based on player type"""
    player_data = await get_player_recent_stats(player_id, num_games)
    
    if "error" in player_data:
        return player_data
    
    player_lookup_result = mlb_stats_client.lookup_player(str(player_id))
    if not player_lookup_result:
         return {"error": f"Could not look up player ID {player_id} for betting stats"}
    player_info = player_lookup_result[0]

    position = player_info.get('primaryPosition', {}).get('abbreviation', 'N/A')
    is_pitcher = position == 'P'
    is_two_way = position == 'TWP'
    
    # For TWP players, we need to get both hitting and pitching stats
    if is_two_way:
        # We already have the stats from get_player_recent_stats
        # But we need to split the calculation for both roles
        
        # First, determine if we have enough games for both roles
        batting_stats = calculate_betting_stats(player_data.get('recent_stats', []), False)
        pitching_stats = calculate_betting_stats(player_data.get('recent_stats', []), True)
        
        player_data['betting_stats'] = {
            'hitting': batting_stats,
            'pitching': pitching_stats
        }
    else:
        betting_stats = calculate_betting_stats(player_data.get('recent_stats', []), is_pitcher)
        player_data['betting_stats'] = betting_stats
    
    player_data['player_type'] = 'TWP' if is_two_way else ('Pitcher' if is_pitcher else 'Batter')
    
    return player_data
