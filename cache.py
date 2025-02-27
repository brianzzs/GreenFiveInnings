import asyncio
import json
import datetime
import statsapi
from functools import lru_cache
from flask import g
import aiohttp
from typing import Dict, List, Any

# In-memory cache for game data
GAME_CACHE: Dict[int, Any] = {}
SCHEDULE_CACHE: Dict[str, List[Any]] = {}


async def fetch_and_cache_game_ids_span(team_id, num_days=None):
    """
    Fetches game IDs for a specified team over a span of days and caches them in the database.
    This function first checks if the game IDs for the specified team and date range are already
    present in the database. If they are, it returns the cached game IDs. If not, it fetches the
    game IDs from an external API, caches them in the database, and then returns the game IDs.
    Args:
        team_id (int): The ID of the team for which to fetch game IDs.
        num_days (int, optional): The number of days before the base date to fetch game IDs for.
                                  If not provided, only the base date's game IDs are fetched.
    Returns:
        list: A list of game IDs for the specified team and date range.
    """
    print("Fetching game IDs")

    cache_key = f"{team_id}_{num_days}"
    if cache_key in SCHEDULE_CACHE:
        return [game["game_id"] for game in SCHEDULE_CACHE[cache_key]]
    # Define the hardcoded base date because the season is OVER
    base_date = datetime.date(2024, 9, 29)
    date_format = "%m/%d/%Y"

    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        dates = []
        current_date = start_date

        while current_date <= base_date:
            end_date = min(current_date + datetime.timedelta(days=4), base_date)
            dates.append(
                {
                    "start_date": current_date.strftime(date_format),
                    "end_date": end_date.strftime(date_format),
                }
            )
            current_date = end_date + datetime.timedelta(days=1)

        # Fetch all schedules concurrently
        tasks = [fetch_schedule(date, team_id) for date in dates]
        all_games = []
        for games in await asyncio.gather(*tasks):
            all_games.extend(games)

        SCHEDULE_CACHE[cache_key] = all_games
        return [game["game_id"] for game in all_games]


async def fetch_schedule(date, team_id):
    # Convert sync function to async using to_thread
    print(
        f"Fetching schedule for team {team_id} from {date['start_date']} to {date['end_date']}"
    )
    return await asyncio.to_thread(
        statsapi.schedule,
        start_date=date["start_date"],
        end_date=date["end_date"],
        team=team_id,
    )


def fetch_and_cache_linescore(game_id):

    game = statsapi.get("game", {"gamePk": game_id})
    linescore_data = game["liveData"]["linescore"]["innings"]

    return linescore_data


async def fetch_game_details_batch(
    game_ids: List[int], session: aiohttp.ClientSession
) -> List[dict]:
    async def fetch_single_game(game_id: int) -> dict:
        if game_id in GAME_CACHE:
            return GAME_CACHE[game_id]

        # Using statsapi through asyncio.to_thread since it's synchronous
        game_data = await asyncio.to_thread(statsapi.get, "game", {"gamePk": game_id})
        GAME_CACHE[game_id] = game_data
        return game_data

    tasks = [fetch_single_game(game_id) for game_id in game_ids]
    return await asyncio.gather(*tasks)


def fetch_game_data(game_id):
    try:
        game = statsapi.get("game", {"gamePk": game_id})
        linescore_data = game["liveData"]["linescore"]["innings"]
        game_data = game["gameData"]

        away_team_id = game_data["teams"]["away"]["id"]
        home_team_id = game_data["teams"]["home"]["id"]
        game_datetime = game_data["datetime"]["dateTime"]
        away_team_runs = sum(inning["away"].get("runs", 0) for inning in linescore_data)
        home_team_runs = sum(inning["home"].get("runs", 0) for inning in linescore_data)
        away_pitcher_id = game_data["probablePitchers"]["away"]["id"]
        home_pitcher_id = game_data["probablePitchers"]["home"]["id"]

        return {
            "game_id": game_id,
            "away_team_id": away_team_id,
            "home_team_id": home_team_id,
            "game_datetime": game_datetime,
            "away_team_runs": away_team_runs,
            "home_team_runs": home_team_runs,
            "away_pitcher_id": away_pitcher_id,
            "home_pitcher_id": home_pitcher_id,
        }

    except Exception as e:
        print(f"Error fetching game data: {e}")
        raise RuntimeError(f"Unable to fetch data for game ID {game_id}")


def fetch_and_cache_pitcher_info(game_id, data=None):

    if not data:
        data = statsapi.get("game", {"gamePk": game_id})

    probable_pitchers = data["gameData"]["probablePitchers"]
    players = data["gameData"]["players"]

    home_pitcher = probable_pitchers.get("home", {"fullName": "TBD", "id": "TBD"})
    away_pitcher = probable_pitchers.get("away", {"fullName": "TBD", "id": "TBD"})

    home_pitcher_hand = players.get(
        "ID" + str(home_pitcher["id"]), {"pitchHand": {"code": "TBD"}}
    )["pitchHand"]["code"]
    away_pitcher_hand = players.get(
        "ID" + str(away_pitcher["id"]), {"pitchHand": {"code": "TBD"}}
    )["pitchHand"]["code"]

    try:
        home_pitcher_stats = statsapi.player_stats(
            home_pitcher["id"], group="pitching", type="season"
        )
        home_pitcher_stats = parse_stats(home_pitcher_stats)
    except Exception:
        home_pitcher_stats = {"wins": "TBD", "losses": "TBD", "era": "TBD"}

    try:
        away_pitcher_stats = statsapi.player_stats(
            away_pitcher["id"], group="pitching", type="season"
        )
        away_pitcher_stats = parse_stats(away_pitcher_stats)
    except Exception:
        away_pitcher_stats = {"wins": "TBD", "losses": "TBD", "era": "TBD"}

    return {
        "homePitcherID": home_pitcher["id"],
        "homePitcher": home_pitcher["fullName"],
        "homePitcherHand": home_pitcher_hand,
        "homePitcherWins": home_pitcher_stats["wins"],
        "homePitcherLosses": home_pitcher_stats["losses"],
        "homePitcherERA": home_pitcher_stats["era"],
        "awayPitcherID": away_pitcher["id"],
        "awayPitcher": away_pitcher["fullName"],
        "awayPitcherHand": away_pitcher_hand,
        "awayPitcherWins": away_pitcher_stats["wins"],
        "awayPitcherLosses": away_pitcher_stats["losses"],
        "awayPitcherERA": away_pitcher_stats["era"],
    }


@lru_cache(maxsize=128)
def parse_stats(stats_string: str) -> dict:
    lines = stats_string.split("\n")
    stats = dict(line.split(": ") for line in lines if ": " in line)
    return {
        "wins": stats.get("wins", "TBD"),
        "losses": stats.get("losses", "TBD"),
        "era": stats.get("era", "TBD"),
    }
