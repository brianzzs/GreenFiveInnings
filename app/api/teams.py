from flask import Blueprint, jsonify
from app.utils.calculations import TEAM_NAMES

teams_bp = Blueprint('teams', __name__, url_prefix='/teams')

@teams_bp.route('/', methods=['GET'])
def get_teams_route():
    """Returns a list of all team names and IDs."""
    return jsonify(TEAM_NAMES)

@teams_bp.route('/<int:team_id>', methods=['GET'])
def get_team_route(team_id):
    """Returns the name for a specific team ID."""
    team_name = TEAM_NAMES.get(team_id)
    if team_name is not None:
        return jsonify({team_id: team_name})
    else:
        return jsonify({"error": "Team not found"}), 404
