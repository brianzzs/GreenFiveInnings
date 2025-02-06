from flask import Flask, jsonify
from flask_cors import CORS
from calculations import TEAM_NAMES, calculate_win_percentage
from preparation import (
    get_nrfi_occurence,
    get_moneyline_scores_first_5_innings,
    get_overs_first_5_innings,
    schedule,
    get_team_stats,
)
from cache import initialize_db
from flask import g


app = Flask(__name__)
app.debug = True
CORS(app)


@app.before_request
def setup():
    initialize_db()


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


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
async def get_stats(team_id: int, num_days: int):
    nrfi = await get_nrfi_occurence(team_id, num_days)
    list_of_results = await get_moneyline_scores_first_5_innings(team_id, num_days)
    win_percentage = calculate_win_percentage(list_of_results, team_id)

    overs_first_5_innings = await get_overs_first_5_innings(team_id, num_days)
    return jsonify(
        {
            "results": list_of_results,
            "win_percentage": win_percentage,
            "nrfi": nrfi,
            "over1_5F5": overs_first_5_innings["over1_5F5"],
            "over2_5F5": overs_first_5_innings["over2_5F5"],
        }
    )


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


if __name__ == "__main__":
    app.run()
