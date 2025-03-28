from functools import lru_cache
from flask import Flask, jsonify
from flask_cors import CORS
from cache import fetch_and_cache_game_ids_span, fetch_game_details_batch
from calculations import TEAM_NAMES, calculate_win_percentage
from preparation import (
    schedule,
    get_team_stats,
    get_next_game_schedule,
    get_today_schedule,
)
import aiohttp
from player import search_player_by_name, get_player_stats, get_player_recent_stats, get_player_betting_stats


app = Flask(__name__)
CORS(app)


@app.route("/teams", methods=["GET"])
def get_teams():
    return jsonify(TEAM_NAMES)


@app.route("/team/<int:team_id>", methods=["GET"])
def get_team(team_id):
    team_name = TEAM_NAMES.get(team_id)
    if team_name is not None:
        return jsonify({team_id: team_name})
    else:
        return jsonify({"error": "Team not found"}), 404


@lru_cache(maxsize=128)
@app.route("/next_schedule/<int:team_id>", methods=["GET"])
def get_next_schedule(team_id):
    return jsonify(get_next_game_schedule(team_id))


@lru_cache(maxsize=128)
@app.route("/schedule/<int:team_id>", methods=["GET"])
def get_schedule(team_id):
    return jsonify(schedule(team_id))


@app.route("/stats/<int:team_id>/<int:num_days>", methods=["GET"])
async def get_stats_batch(team_id: int, num_days: int) -> dict:
    async with aiohttp.ClientSession() as session:
        game_ids = await fetch_and_cache_game_ids_span(team_id, num_days)

        game_details = await fetch_game_details_batch(game_ids, session)

        first_inning_runs = []
        team_runs_f5 = []
        moneyline_results = []

        for game in game_details:
            linescore = game["liveData"]["linescore"]["innings"]
            game_data = game["gameData"]

            probable_pitchers = game["gameData"]["probablePitchers"]
            players = game["gameData"]["players"]

            home_pitcher = probable_pitchers.get(
                "home", {"fullName": "TBD", "id": "TBD"}
            )
            away_pitcher = probable_pitchers.get(
                "away", {"fullName": "TBD", "id": "TBD"}
            )

            home_pitcher_hand = players.get(
                "ID" + str(home_pitcher["id"]), {"pitchHand": {"code": "TBD"}}
            )["pitchHand"]["code"]

            away_pitcher_hand = players.get(
                "ID" + str(away_pitcher["id"]), {"pitchHand": {"code": "TBD"}}
            )["pitchHand"]["code"]

            if linescore:
                first_inning = linescore[0]
                runs = (
                    first_inning["home"]["runs"]
                    if game_data["teams"]["home"]["id"] == team_id
                    else first_inning["away"]["runs"]
                )
                first_inning_runs.append(runs)

            f5_innings = linescore[:5]
            team_runs = sum(
                (
                    inning["home"]["runs"]
                    if game_data["teams"]["home"]["id"] == team_id
                    else inning["away"]["runs"]
                )
                for inning in f5_innings
            )
            team_runs_f5.append(team_runs)

            moneyline_results.append(
                {
                    "game_date": game_data["datetime"]["originalDate"],
                    "away_team": {
                        "id": game_data["teams"]["away"]["id"],
                        "name": TEAM_NAMES.get(
                            game_data["teams"]["away"]["id"], "TBD"
                        ),
                        "runs": [inning["away"]["runs"] for inning in f5_innings],
                        "probable_pitcher": {
                            "name": away_pitcher["fullName"],
                            "id": away_pitcher["id"],
                            "hand": away_pitcher_hand,
                        },
                        "total_runs": sum(
                            inning["away"]["runs"] for inning in f5_innings
                        ),
                    },
                    "home_team": {
                        "id": game_data["teams"]["home"]["id"],
                        "name": TEAM_NAMES.get(
                            game_data["teams"]["home"]["id"], "TBD"
                        ),
                        "runs": [inning["home"]["runs"] for inning in f5_innings],
                        "probable_pitcher": {
                            "name": home_pitcher["fullName"],
                            "id": home_pitcher["id"],
                            "hand": home_pitcher_hand,
                        },
                        "total_runs": sum(
                            inning["home"]["runs"] for inning in f5_innings
                        ),
                    },
                }
            )

        nrfi_occurrence = (
            sum(1 for runs in first_inning_runs if runs == 0)
            / len(first_inning_runs)
            * 100
            if first_inning_runs
            else 0
        )

        over_1_5 = (
            sum(1 for runs in team_runs_f5 if runs >= 1.5) / len(team_runs_f5) * 100
            if team_runs_f5
            else 0
        )
        over_2_5 = (
            sum(1 for runs in team_runs_f5 if runs >= 2.5) / len(team_runs_f5) * 100
            if team_runs_f5
            else 0
        )

        win_percentage = calculate_win_percentage(moneyline_results, team_id)

        return {
            "results": moneyline_results,
            "nrfi": round(nrfi_occurrence, 2),
            "win_percentage": round(win_percentage, 2),
            "over1_5F5": round(over_1_5, 2),
            "over2_5F5": round(over_2_5, 2),
        }


@app.route("/today_schedule", methods=["GET"])
def today_schedule():
    return jsonify(get_today_schedule())


@app.route("/player/search/<string:name>", methods=["GET"])
def search_player(name):
    return jsonify(search_player_by_name(name))


@app.route("/player/stats/<int:player_id>/<string:season>", methods=["GET"])
def get_player(player_id, season):
    return jsonify(get_player_stats(player_id, season))


@app.route("/player/recent-stats/<int:player_id>/<int:num_days>", methods=["GET"])
async def get_recent_player_stats(player_id, num_days):
    stats = await get_player_recent_stats(player_id, num_days)
    return jsonify(stats)


@app.route("/player/betting-stats/<int:player_id>/<int:num_games>", methods=["GET"])
async def get_player_betting_stats_route(player_id, num_games):
    stats = await get_player_betting_stats(player_id, num_games)
    return jsonify(stats)


if __name__ == "__main__":
    app.run(debug=False)  
