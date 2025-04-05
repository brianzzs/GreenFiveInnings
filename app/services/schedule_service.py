import asyncio
import datetime
from typing import Dict, List, Any
from app.clients import mlb_stats_client
from cache import SCHEDULE_CACHE 
import pytz
from functools import lru_cache
from app.clients import mlb_stats_client
from app.services import game_service, player_service 
from app.utils.helpers import convert_utc_to_local
from app.utils import helpers


async def fetch_schedule(date, team_id):
    """Internal helper to fetch schedule for a specific date range."""

    # This uses the async wrapper from the client
    return await mlb_stats_client.get_schedule_async(
        start_date=date["start_date"],
        end_date=date["end_date"],
        team_id=team_id,
    )

async def fetch_and_cache_game_ids_span(team_id: int, num_days: int = None) -> List[int]:
    """
    Fetches game IDs for a specified team over a span of days, utilizing cache.
    Args:
        team_id: The ID of the team.
        num_days: The number of past days to fetch games for.
    Returns:
        A list of game IDs.
    """
    cache_key = f"{team_id}_{num_days}"
    if cache_key in SCHEDULE_CACHE:
        return [game["game_id"] for game in SCHEDULE_CACHE[cache_key]]
    
    base_date = datetime.date.today() - datetime.timedelta(days=1) 
    date_format = "%m/%d/%Y"
    all_games = []

    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        dates_to_fetch = []
        current_date = start_date

        while current_date <= base_date:
            end_date = min(current_date + datetime.timedelta(days=4), base_date)
            dates_to_fetch.append(
                {
                    "start_date": current_date.strftime(date_format),
                    "end_date": end_date.strftime(date_format),
                }
            )
            current_date = end_date + datetime.timedelta(days=1)

        tasks = [fetch_schedule(date_info, team_id) for date_info in dates_to_fetch]
        
        results = await asyncio.gather(*tasks)
        for games_chunk in results:
            all_games.extend(games_chunk)
    else:
        start_date_str = base_date.strftime(date_format)
        all_games = await fetch_schedule({"start_date": start_date_str, "end_date": start_date_str}, team_id)

    SCHEDULE_CACHE[cache_key] = all_games
    
    return [game["game_id"] for game in all_games]


@lru_cache(maxsize=1) 
def _get_team_records_from_standings() -> Dict[int, str]:
    """Fetches current standings and returns a dict mapping team ID to 'W-L' record."""
    records = {}
    try:
        standings_data = mlb_stats_client.get_standings(league_id="103,104")
        
        for division_id, division_data in standings_data.items():
            if isinstance(division_data, dict) and 'teams' in division_data:
                for team_standings in division_data['teams']:
                    team_id = team_standings.get('team_id')
                    wins = team_standings.get('w')
                    losses = team_standings.get('l')
                    if team_id is not None and wins is not None and losses is not None:
                        records[team_id] = f"{wins}-{losses}"
    except Exception as e:
        print(f"Error parsing standings data: {e}")
        _get_team_records_from_standings.cache_clear()
        
    if not records:
        print("Warning: Could not retrieve or parse team records from standings.")
        _get_team_records_from_standings.cache_clear()
        
    return records


def get_today_schedule() -> List[Dict]:
    """Gets the schedule for today, including pitcher info and team records."""
    processed_games = []
    try:
        team_records = _get_team_records_from_standings()
        today_date = datetime.date.today()
        today_date_str = today_date.strftime("%Y-%m-%d")
        raw_games = mlb_stats_client.get_schedule(
            start_date=today_date_str, 
            end_date=today_date_str
        )

        if not raw_games:
            return []

        for game in raw_games:
            try:
                game_status = game.get("status") 
                game_id = game.get("game_id")
                home_id = game.get("home_id")
                away_id = game.get("away_id")
                game_time_utc_str = game.get("game_datetime")

                if not game_id or not home_id or not away_id or game_status in ["Final", "Game Over", "Completed Early"]:
                    continue

                try:
                    game_time_utc = datetime.datetime.strptime(game_time_utc_str, "%Y-%m-%dT%H:%M:%SZ")
                    game_time_utc = pytz.UTC.localize(game_time_utc)
                    game_time_local = game_time_utc.astimezone(pytz.timezone('America/New_York'))
                    if game_time_local.date() != today_date:
                        continue
                except Exception as e:
                    print(f"[get_today_schedule] Error converting game time: {e}")
                    continue

                away_record_str = team_records.get(away_id, "0-0") 
                home_record_str = team_records.get(home_id, "0-0") 

                pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)

                processed_game = {
                    "game_id": game_id,
                    "home_team_id": home_id,
                    "home_team_name": game.get("home_name"),
                    "home_team_record": home_record_str, 
                    "away_team_id": away_id,
                    "away_team_name": game.get("away_name"),
                    "away_team_record": away_record_str, 
                    "status": game_status,
                    "game_datetime": game_time_utc_str, 
                    "venue": game.get("venue_name", "TBD"), 
                    **pitcher_info
                }
                processed_games.append(processed_game)

            except Exception as inner_e:
                 print(f"[get_today_schedule] Error processing game data: {game}. Error: {inner_e}")

        return processed_games
    except Exception as e:
        print(f"[get_today_schedule] Error fetching or processing today's schedule: {e}")
        return []

@lru_cache(maxsize=128)
def get_schedule_for_team(team_id: int, num_days: int = None) -> List[Dict]:
    """Gets historical schedule for a team up to num_days ago, including pitcher info and team records."""
    base_date = datetime.date.today()
    date_format = "%Y-%m-%d" 

    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        formatted_start_date = start_date.strftime(date_format)
    else:
        formatted_start_date = base_date.strftime(date_format)

    formatted_end_date = base_date.strftime(date_format)

    try:
        team_records = _get_team_records_from_standings() # Get records dict
        # Fetch schedule 
        schedule_summary = mlb_stats_client.get_schedule(
            start_date=formatted_start_date, 
            end_date=formatted_end_date, 
            team_id=team_id
        )

        if not schedule_summary:
            next_day_start = base_date + datetime.timedelta(days=1)
            formatted_next_start = next_day_start.strftime(date_format)
            schedule_summary = mlb_stats_client.get_schedule(
                start_date=formatted_next_start, 
                end_date=formatted_next_start, 
                team_id=team_id
            )
            if not schedule_summary:
                return []

        games_with_pitcher_info = []
        for game in schedule_summary: 
            try:
                game_id = game.get("game_id")
                home_id = game.get("home_id")
                away_id = game.get("away_id")
                if not game_id or not home_id or not away_id:
                    continue
                
                away_record_str = team_records.get(away_id, "0-0") # Default if lookup fails
                home_record_str = team_records.get(home_id, "0-0") # Default if lookup fails

                pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)
                game_time_utc_str = game.get("game_datetime")
                processed_game = {
                    "game_id": game_id,
                    "home_team_id": home_id,
                    "home_team_name": game.get("home_name"),
                    "home_team_record": home_record_str, 
                    "away_team_id": away_id,
                    "away_team_name": game.get("away_name"),
                    "away_team_record": away_record_str, 
                    "status": game.get("status"),
                    "game_datetime": game_time_utc_str,
                    "venue": game.get("venue_name", "TBD"),
                    **pitcher_info 
                }
                games_with_pitcher_info.append(processed_game)

            except Exception as inner_e:
                 print(f"[get_schedule_for_team] Error processing game data: {game}. Error: {inner_e}")

        return games_with_pitcher_info

    except Exception as e:
        print(f"[get_schedule_for_team] Error getting schedule for team {team_id}: {e}")
        return []

@lru_cache(maxsize=128)
def get_next_game_schedule_for_team(team_id: int) -> List[Dict]:
    """Gets the upcoming schedule (today or tomorrow) for a team, including pitcher info and team records."""
    base_date = datetime.date.today()
    date_format = "%Y-%m-%d"
    formatted_today = base_date.strftime(date_format)
    team_param = team_id if team_id != 0 else None
    games_with_pitcher_info = [] 

    try:
        team_records = _get_team_records_from_standings()

        print(f"[get_next_game_schedule] Checking today ({formatted_today}) for team {team_id}")
        todays_games = mlb_stats_client.get_schedule(
            start_date=formatted_today,
            end_date=formatted_today,
            team_id=team_param
        )

        if todays_games:
            for game in todays_games:
                try:
                    game_id = game.get("game_id")
                    home_id = game.get("home_id")
                    away_id = game.get("away_id")
                    if not game_id or not home_id or not away_id:
                        continue

                    game_status = game.get("status")
                    # Skip games that are already finished
                    if game_status in ["Final", "Game Over", "Completed Early"]:
                        continue

                    away_record_str = team_records.get(away_id, "0-0")
                    home_record_str = team_records.get(home_id, "0-0")
                    pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)
                    game_time_utc_str = game.get("game_datetime")

                    processed_game = {
                        "game_id": game_id,
                        "home_team_id": home_id,
                        "home_team_name": game.get("home_name"),
                        "home_team_record": home_record_str,
                        "away_team_id": away_id,
                        "away_team_name": game.get("away_name"),
                        "away_team_record": away_record_str,
                        "status": game_status,
                        "game_datetime": game_time_utc_str,
                        "venue": game.get("venue_name", "TBD"),
                        **pitcher_info
                    }
                    games_with_pitcher_info.append(processed_game)


                except Exception as inner_e:
                    print(f"[get_next_game_schedule] Error processing game data (today): {game}. Error: {inner_e}")
        else:
             print(f"[get_next_game_schedule] No games found for team {team_id} today.")

        if not games_with_pitcher_info:
            print(f"[get_next_game_schedule] No upcoming games found today, checking tomorrow...")
            next_date = base_date + datetime.timedelta(days=1)
            formatted_tomorrow = next_date.strftime(date_format)
            tomorrows_games = mlb_stats_client.get_schedule(
                start_date=formatted_tomorrow,
                end_date=formatted_tomorrow,
                team_id=team_param
            )
            
            if tomorrows_games:
                for game in tomorrows_games:
                    try:
                        game_id = game.get("game_id")
                        home_id = game.get("home_id")
                        away_id = game.get("away_id")
                        if not game_id or not home_id or not away_id:
                            continue

                        game_status = game.get("status")
                        if game_status in ["Final", "Game Over", "Completed Early"]:
                            continue
                        
                        away_record_str = team_records.get(away_id, "0-0")
                        home_record_str = team_records.get(home_id, "0-0")
                        pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)
                        game_time_utc_str = game.get("game_datetime")

                        processed_game = {
                             "game_id": game_id,
                             "home_team_id": home_id,
                             "home_team_name": game.get("home_name"),
                             "home_team_record": home_record_str,
                             "away_team_id": away_id,
                             "away_team_name": game.get("away_name"),
                             "away_team_record": away_record_str,
                             "status": game_status,
                             "game_datetime": game_time_utc_str,
                             "venue": game.get("venue_name", "TBD"),
                             **pitcher_info
                        }
                        games_with_pitcher_info.append(processed_game)
                        # Optional: break here if you only want the single next game.
                        # break

                    except Exception as inner_e:
                        print(f"[get_next_game_schedule] Error processing game data (tomorrow): {game}. Error: {inner_e}")
            else:
                 print(f"[get_next_game_schedule] No games found for team {team_id} tomorrow either.")

        if not games_with_pitcher_info:
             print(f"[get_next_game_schedule] Final result: No upcoming games found for team {team_id} today or tomorrow.")
             
        return games_with_pitcher_info

    except Exception as e:
        print(f"[get_next_game_schedule] Error getting next game schedule for team {team_id}: {e}")
        return []

async def fetch_last_n_completed_game_ids(team_id: int, num_games: int) -> List[int]:
    """
    Fetches the game IDs for the last 'num_games' completed games for a specific team.

    Args:
        team_id: The ID of the team.
        num_games: The number of completed games to retrieve.

    Returns:
        A list of game IDs for the most recent completed games, sorted newest first.
        Returns an empty list if the team ID is invalid or no games are found.
    """
    if not team_id:
        return []

    completed_games = []
    current_year = datetime.date.today().year
    year_start_date = datetime.date(current_year, 1, 1)
    end_date = datetime.date.today() 
    days_to_check_increment = 15 
    total_days_checked = 0
    date_format = "%Y-%m-%d"

    while len(completed_games) < num_games and end_date >= year_start_date:
        start_date = max(end_date - datetime.timedelta(days=days_to_check_increment -1), year_start_date)
        start_date_str = start_date.strftime(date_format)
        end_date_str = end_date.strftime(date_format)
        
        # Prevent infinite loop if start/end date become the same at year boundary
        if start_date == end_date and total_days_checked > 0: 
             break


        try:
            schedule_chunk = await mlb_stats_client.get_schedule_async(
                team_id=team_id,
                start_date=start_date_str,
                end_date=end_date_str
            )

            for game in schedule_chunk:
                game_status = game.get('status')
                game_type = game.get('game_type') # Get game type
                if game_status in ["Final", "Game Over", "Completed Early"] and game_type in ['R', 'S'] and game.get('game_id'):
                    if game['game_id'] not in [g['game_id'] for g in completed_games]:
                        completed_games.append({
                            'game_id': game['game_id'],
                            'game_datetime': game['game_datetime']
                        })

            completed_games.sort(key=lambda x: x['game_datetime'], reverse=True)

            end_date = start_date - datetime.timedelta(days=1)
            total_days_checked += (end_date - start_date).days + 1 

        except Exception as e:
            print(f"[fetch_last_n_completed_game_ids] Error fetching schedule chunk for team {team_id}: {e}")
            break 

    if not completed_games:
        print(f"[fetch_last_n_completed_game_ids] No completed R or S games found for team {team_id} since {year_start_date}.")

    return [game['game_id'] for game in completed_games[:num_games]]

