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

    # Store fetched games in cache
    SCHEDULE_CACHE[cache_key] = all_games
    
    return [game["game_id"] for game in all_games]


@lru_cache(maxsize=128)
def get_today_schedule() -> List[Dict]:
    """Gets the schedule for today, including pitcher info."""
    processed_games = []
    try:
        today_date = datetime.date.today()
        today_date_str = today_date.strftime("%Y-%m-%d")

        raw_games = mlb_stats_client.get_schedule(start_date=today_date_str, end_date=today_date_str)

        if not raw_games:
            return []

        games_before_processing = 0
        for game in raw_games:
            try:
                game_status = game.get("status") 
                game_id = game.get("game_id")

                if not game_id:
                     continue
                
                if game_status in ["Final", "Game Over", "Completed Early"]:
                    continue

                games_before_processing += 1
                pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)

                game_time_utc_str = game.get("game_datetime") 

                processed_game = {
                    "game_id": game_id,
                    "home_team_id": game.get("home_id"),
                    "home_team_name": game.get("home_name"),
                    "away_team_id": game.get("away_id"),
                    "away_team_name": game.get("away_name"),
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
    """Gets historical schedule for a team up to num_days ago, including pitcher info."""
    base_date = datetime.date.today()
    date_format = "%Y-%m-%d" 

    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        formatted_start_date = start_date.strftime(date_format)
    else:
        formatted_start_date = base_date.strftime(date_format)

    formatted_end_date = base_date.strftime(date_format)

    try:
        schedule_summary = mlb_stats_client.get_schedule(
            start_date=formatted_start_date, end_date=formatted_end_date, team_id=team_id
        )

        if not schedule_summary:
            next_day_start = base_date + datetime.timedelta(days=1)
            formatted_next_start = next_day_start.strftime(date_format)
            schedule_summary = mlb_stats_client.get_schedule(
                start_date=formatted_next_start, end_date=formatted_next_start, team_id=team_id 
            )
            if not schedule_summary:
                return []

        games_with_pitcher_info = []
        for game in schedule_summary: 
            try:
                game_id = game.get("game_id")
                if not game_id:
                    continue
                pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)
                game_time_utc_str = game.get("game_datetime")
                processed_game = {
                    "game_id": game_id,
                    "home_team_id": game.get("home_id"),
                    "home_team_name": game.get("home_name"),
                    "away_team_id": game.get("away_id"),
                    "away_team_name": game.get("away_name"),
                    "status": game.get("status"),
                    "game_datetime": game_time_utc_str,
                    "venue": game.get("venue_name", "TBD"),
                    **pitcher_info # Merge pitcher info
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
    """Gets the upcoming schedule (today or tomorrow) for a team, including pitcher info."""
    base_date = datetime.date.today()
    date_format = "%Y-%m-%d" 
    formatted_today = base_date.strftime(date_format)
    team_param = team_id if team_id != 0 else None

    try:
        # Try fetching today's schedule first with correct date format
        next_games_summary = mlb_stats_client.get_schedule(start_date=formatted_today, end_date=formatted_today, team_id=team_param)

        # If no games today, look for tomorrow's games
        if not next_games_summary:
            next_date = base_date + datetime.timedelta(days=1)
            formatted_tomorrow = next_date.strftime(date_format)
            next_games_summary = mlb_stats_client.get_schedule(start_date=formatted_tomorrow, end_date=formatted_tomorrow, team_id=team_param)

        if not next_games_summary:
            return []

        games_with_pitcher_info = []
        for game in next_games_summary: 
            try:
                game_id = game.get("game_id")
                if not game_id:
                    continue

                game_status = game.get("status")
                if game_status in ["Final", "Game Over", "Completed Early"]:
                    continue
                    
                pitcher_info = player_service.fetch_and_cache_pitcher_info(game_id)
                game_time_utc_str = game.get("game_datetime")

                processed_game = {
                    "game_id": game_id,
                    "home_team_id": game.get("home_id"),
                    "home_team_name": game.get("home_name"),
                    "away_team_id": game.get("away_id"),
                    "away_team_name": game.get("away_name"),
                    "status": game_status,
                    "game_datetime": game_time_utc_str, # Send UTC string
                    "venue": game.get("venue_name", "TBD"),
                    **pitcher_info # Merge pitcher info
                }
                games_with_pitcher_info.append(processed_game)

            except Exception as inner_e:
                 print(f"[get_next_game_schedule] Error processing game data: {game}. Error: {inner_e}")

        return games_with_pitcher_info

    except Exception as e:
        print(f"[get_next_game_schedule] Error getting next game schedule for team {team_id}: {e}")
        return []

