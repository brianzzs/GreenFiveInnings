from flask import Flask, jsonify
from flask_cors import CORS
from cache import fetch_and_cache_game_ids_span, fetch_game_details_batch
from calculations import TEAM_NAMES, calculate_win_percentage
from preparation import (
    schedule,
    get_team_stats,
)
import aiohttp
from player import search_player_by_name, get_player_stats


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
                "ID" + str(home_pitcher["id"]), {"pitchHand": {"code": "Unknown"}}
            )["pitchHand"]["code"]

            away_pitcher_hand = players.get(
                "ID" + str(away_pitcher["id"]), {"pitchHand": {"code": "Unknown"}}
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
                    "away_team": {
                        "id": game_data["teams"]["away"]["id"],
                        "name": TEAM_NAMES.get(
                            game_data["teams"]["away"]["id"], "Unknown"
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
                            game_data["teams"]["home"]["id"], "Unknown"
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



@app.route("/schedule_today", methods=["GET"])
def get_schedule_today():
    return jsonify(schedule(0))


@app.route("/compare-teams/<int:team_id1>/<int:team_id2>", methods=["GET"])
def compare_teams(team_id1, team_id2):
    stats_team1 = get_team_stats(team_id1, 20)
    stats_team2 = get_team_stats(team_id2, 20)

    combined_stats = {
        "team1": {"id": team_id1, "stats": stats_team1},
        "team2": {"id": team_id2, "stats": stats_team2},
    }
    return combined_stats

@app.route("/player/search/<string:name>", methods=["GET"])
def search_player(name):
    return jsonify(search_player_by_name(name))


@app.route("/player/stats/<int:player_id>", methods=["GET"])
def get_player(player_id):
    return jsonify(get_player_stats(player_id))


if __name__ == "__main__":
    # print(app.url_map)
    app.run(debug=True)  
