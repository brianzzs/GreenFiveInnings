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
    db.commit()


def fetch_and_cache_game_ids_span(team_id, num_days):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT id FROM tb_GameId
        WHERE game_datetime >= datetime('now', ? || ' days')
    """,
        (str(-num_days),),
    )

    result = cursor.fetchall()
    if result:
        return [game[0] for game in result]

    # formatted_start_date = (datetime.date.today() - datetime.timedelta(days=num_days)).strftime("%m/%d/%Y")
    # formatted_end_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%m/%d/%Y")

    formatted_start_date = "09/15/2023"
    formatted_end_date = "10/1/2023"
    last_n_days_games = statsapi.schedule(
        start_date=formatted_start_date, end_date=formatted_end_date, team=team_id
    )

    game_ids = []
    for game in last_n_days_games:
        game_id = game["game_id"]
        game_datetime = game["game_datetime"]
        cursor.execute(
            """
            INSERT OR IGNORE INTO tb_GameId (id, game_datetime)
            VALUES (?, ?)
        """,
            (game_id, game_datetime),
        )
        game_ids.append(game_id)

    db.commit()
    return game_ids


def fetch_and_cache_linescore(game_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT linescore FROM tb_Linescores WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()

    if result:
        return json.loads(result[0])

    # Fetch data from the API
    game = statsapi.get("game", {"gamePk": game_id})
    linescore_data = game["liveData"]["linescore"]["innings"]

    cursor.execute(
        "INSERT INTO tb_Linescores (game_id, linescore) VALUES (?, ?)",
        (game_id, json.dumps(linescore_data)),
    )

    db.commit()

    return linescore_data


def fetch_game_data(game_id):
    db = get_db()
    cursor = db.cursor()

    # Check if data is already cached
    cursor.execute(
        """
        SELECT 
            game_id, away_team_id, home_team_id, game_datetime,
            away_team_runs, home_team_runs, away_pitcher_id, home_pitcher_id
        FROM tb_GameData WHERE game_id = ?
        """,
        (game_id,),
    )
    result = cursor.fetchone()

    if result:
        # Return cached data
        return {
            "game_id": result["game_id"],
            "away_team_id": result["away_team_id"],
            "home_team_id": result["home_team_id"],
            "game_datetime": result["game_datetime"],
            "away_team_runs": result["away_team_runs"],
            "home_team_runs": result["home_team_runs"],
            "away_pitcher_id": result["away_pitcher_id"],
            "home_pitcher_id": result["home_pitcher_id"],
        }

    # Fetch data from the API
    try:
        game = statsapi.get("game", {"gamePk": game_id})
        linescore_data = game["liveData"]["linescore"]["innings"]
        game_data = game["gameData"]

        # Extract required data
        away_team_id = game_data["teams"]["away"]["id"]
        home_team_id = game_data["teams"]["home"]["id"]
        game_datetime = game_data["datetime"]["dateTime"]
        away_team_runs = sum(inning["away"].get("runs", 0) for inning in linescore_data)
        home_team_runs = sum(inning["home"].get("runs", 0) for inning in linescore_data)
        away_pitcher_id = game_data["probablePitchers"]["away"]["id"]
        home_pitcher_id = game_data["probablePitchers"]["home"]["id"]

        # Cache the fetched data in the database
        cursor.execute(
            """
            INSERT OR IGNORE INTO tb_GameData (
                game_id, away_team_id, home_team_id, game_datetime,
                away_team_runs, home_team_runs, away_pitcher_id, home_pitcher_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                away_team_id,
                home_team_id,
                game_datetime,
                away_team_runs,
                home_team_runs,
                away_pitcher_id,
                home_pitcher_id,
            ),
        )
        db.commit()

        # Return the fetched data
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
