import asyncio
import json
import datetime
import statsapi
from flask import g
import sqlite3


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("temp_linescores.db")
        g.db.row_factory = sqlite3.Row  # Optional: Allows for dictionary-like access
    return g.db


def initialize_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_Linescores (
            game_id INTEGER PRIMARY KEY,
            linescore TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_GameId (
            id INTEGER PRIMARY KEY,
            game_datetime TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_GameData (
            game_id INTEGER PRIMARY KEY,
            away_team_id INTEGER,
            home_team_id INTEGER,
            game_datetime TEXT,
            away_team_runs INTEGER,
            home_team_runs INTEGER,
            away_pitcher_id INTEGER,
            home_pitcher_id INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_PitcherData (
            game_id INTEGER PRIMARY KEY,
            home_pitcher_id INTEGER,
            home_pitcher_name TEXT,
            home_pitcher_hand TEXT,
            home_pitcher_wins TEXT,
            home_pitcher_losses TEXT,
            home_pitcher_era TEXT,
            away_pitcher_id INTEGER,
            away_pitcher_name TEXT,
            away_pitcher_hand TEXT,
            away_pitcher_wins TEXT,
            away_pitcher_losses TEXT,
            away_pitcher_era TEXT
        )
        """
    )
    db.commit()


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
    # db = get_db()
    # cursor = db.cursor()

    # Define the hardcoded base date
    base_date = datetime.date(2024, 9, 29)

    # If num_days is provided, calculate start date dynamically
    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        formatted_start_date = start_date.strftime("%m/%d/%Y")
    else:
        formatted_start_date = base_date.strftime("%m/%d/%Y")

    # Calculate end_date dynamically for num_days
    end_date = base_date
    formatted_end_date = end_date.strftime("%m/%d/%Y")

    # Check if data exists in the database
    # cursor.execute(
    #     """
    #     SELECT id FROM tb_GameId
    #     WHERE game_datetime >= ? AND game_datetime <= ?
    #     """,
    #     (formatted_start_date, formatted_end_date),
    # )
    # result = cursor.fetchall()

    # if result:
    #     return [game["id"] for game in result]

    # If not in the database, fetch from the API
    dates = []
    end_date = start_date - datetime.timedelta(days=1)

    # Creating a list of dates to fetch in batches of 5 days
    for i in range(0, (num_days + 1) // 5):
        start_date = end_date + datetime.timedelta(days=1)
        end_date = start_date + datetime.timedelta(days=5)
        dates.append(
            {
                "start_date": start_date.strftime("%m/%d/%Y"),
                "end_date": end_date.strftime("%m/%d/%Y"),
            }
        )

    print("Fetching game IDs from API asynchronously, this may take a while...")
    print(f"start time: {datetime.datetime.now()}")
    last_n_days_games = [fetch_schedule(date, team_id) for date in dates]
    tasks = await asyncio.gather(*last_n_days_games)
    results = []
    for task in tasks:
        results.extend(task)
    print(f"Found {len(results)} games for team {team_id} in the last {num_days} days")
    
    game_ids = []
    for game in results:
        game_id = game["game_id"]
        game_datetime = game["game_datetime"]
        # cursor.execute(
        #     """
        #     INSERT OR IGNORE INTO tb_GameId (id, game_datetime)
        #     VALUES (?, ?)
        #     """,
        #     (game_id, game_datetime),
        # )
        game_ids.append(game_id)

    print("Game IDs fetched successfully")
    print(f"end time: {datetime.datetime.now()}")
    # db.commit()
    return game_ids


async def fetch_schedule(date, team_id):
    # Convert sync function to async using to_thread
    print(f"Fetching schedule for team {team_id} from {date['start_date']} to {date['end_date']}")
    return await asyncio.to_thread(
        statsapi.schedule,
        start_date=date["start_date"],
        end_date=date["end_date"],
        team=team_id,
    )


def fetch_and_cache_linescore(game_id):
    # db = get_db()
    # cursor = db.cursor()

    # cursor.execute("SELECT linescore FROM tb_Linescores WHERE game_id = ?", (game_id,))
    # result = cursor.fetchone()

    # if result:
    #     return json.loads(result[0])

    # Fetch data from the API
    game = statsapi.get("game", {"gamePk": game_id})
    linescore_data = game["liveData"]["linescore"]["innings"]

    # cursor.execute(
    #     "INSERT INTO tb_Linescores (game_id, linescore) VALUES (?, ?)",
    #     (game_id, json.dumps(linescore_data)),
    # )

    # db.commit()

    return linescore_data


def fetch_game_data(game_id):
    # db = get_db()
    # cursor = db.cursor()

    # cursor.execute(
    #     """
    #     SELECT 
    #         game_id, away_team_id, home_team_id, game_datetime,
    #         away_team_runs, home_team_runs, away_pitcher_id, home_pitcher_id
    #     FROM tb_GameData WHERE game_id = ?
    #     """,
    #     (game_id,),
    # )
    # result = cursor.fetchone()

    # if result:
    #     return {
    #         "game_id": result["game_id"],
    #         "away_team_id": result["away_team_id"],
    #         "home_team_id": result["home_team_id"],
    #         "game_datetime": result["game_datetime"],
    #         "away_team_runs": result["away_team_runs"],
    #         "home_team_runs": result["home_team_runs"],
    #         "away_pitcher_id": result["away_pitcher_id"],
    #         "home_pitcher_id": result["home_pitcher_id"],
    #     }

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

        # cursor.execute(
        #     """
        #     INSERT OR IGNORE INTO tb_GameData (
        #         game_id, away_team_id, home_team_id, game_datetime,
        #         away_team_runs, home_team_runs, away_pitcher_id, home_pitcher_id
        #     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        #     """,
        #     (
        #         game_id,
        #         away_team_id,
        #         home_team_id,
        #         game_datetime,
        #         away_team_runs,
        #         home_team_runs,
        #         away_pitcher_id,
        #         home_pitcher_id,
        #     ),
        # )
        # db.commit()

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
    # db = get_db()
    # cursor = db.cursor()

    # cursor.execute(
    #     """
    #     SELECT 
    #         home_pitcher_id, home_pitcher_name, home_pitcher_hand, 
    #         home_pitcher_wins, home_pitcher_losses, home_pitcher_era,
    #         away_pitcher_id, away_pitcher_name, away_pitcher_hand, 
    #         away_pitcher_wins, away_pitcher_losses, away_pitcher_era
    #     FROM tb_PitcherData WHERE game_id = ?
    #     """,
    #     (game_id,),
    # )
    # result = cursor.fetchone()

    # if result:
    #     return {
    #         "homePitcherID": result["home_pitcher_id"],
    #         "homePitcher": result["home_pitcher_name"],
    #         "homePitcherHand": result["home_pitcher_hand"],
    #         "homePitcherWins": result["home_pitcher_wins"],
    #         "homePitcherLosses": result["home_pitcher_losses"],
    #         "homePitcherERA": result["home_pitcher_era"],
    #         "awayPitcherID": result["away_pitcher_id"],
    #         "awayPitcher": result["away_pitcher_name"],
    #         "awayPitcherHand": result["away_pitcher_hand"],
    #         "awayPitcherWins": result["away_pitcher_wins"],
    #         "awayPitcherLosses": result["away_pitcher_losses"],
    #         "awayPitcherERA": result["away_pitcher_era"],
    #     }

    if not data:
        data = statsapi.get("game", {"gamePk": game_id})

    probable_pitchers = data["gameData"]["probablePitchers"]
    players = data["gameData"]["players"]

    home_pitcher = probable_pitchers.get("home", {"fullName": "TBD", "id": "TBD"})
    away_pitcher = probable_pitchers.get("away", {"fullName": "TBD", "id": "TBD"})

    home_pitcher_hand = players.get(
        "ID" + str(home_pitcher["id"]), {"pitchHand": {"code": "Unknown"}}
    )["pitchHand"]["code"]
    away_pitcher_hand = players.get(
        "ID" + str(away_pitcher["id"]), {"pitchHand": {"code": "Unknown"}}
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

    # cursor.execute(
    #     """
    #     INSERT OR IGNORE INTO tb_PitcherData (
    #         game_id, 
    #         home_pitcher_id, home_pitcher_name, home_pitcher_hand, 
    #         home_pitcher_wins, home_pitcher_losses, home_pitcher_era, 
    #         away_pitcher_id, away_pitcher_name, away_pitcher_hand, 
    #         away_pitcher_wins, away_pitcher_losses, away_pitcher_era
    #     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    #     """,
    #     (
    #         game_id,
    #         home_pitcher["id"],
    #         home_pitcher["fullName"],
    #         home_pitcher_hand,
    #         home_pitcher_stats["wins"],
    #         home_pitcher_stats["losses"],
    #         home_pitcher_stats["era"],
    #         away_pitcher["id"],
    #         away_pitcher["fullName"],
    #         away_pitcher_hand,
    #         away_pitcher_stats["wins"],
    #         away_pitcher_stats["losses"],
    #         away_pitcher_stats["era"],
    #     ),
    # )
    # db.commit()

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


def parse_stats(stats_string):
    lines = stats_string.split("\n")
    stats = {}

    for line in lines:
        parts = line.split(": ")
        if len(parts) == 2:
            key, value = parts
            stats[key] = value

    pitcher_stats = {
        "wins": stats.get("wins", "Unknown"),
        "losses": stats.get("losses", "Unknown"),
        "era": stats.get("era", "Unknown"),
    }

    return pitcher_stats
