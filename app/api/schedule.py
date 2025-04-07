from flask import Blueprint, jsonify
from app.services import schedule_service, game_service
from functools import lru_cache

schedule_bp = Blueprint('schedule', __name__)  



@schedule_bp.route('/today_schedule', methods=['GET'])
@lru_cache(maxsize=128)
def today_schedule_route():
    """Gets the schedule for today, including pitcher info."""
    return jsonify(schedule_service.get_today_schedule())

@schedule_bp.route('/schedule/<int:team_id>', methods=['GET'])
@lru_cache(maxsize=128)
def get_schedule_route(team_id):
    """Gets historical schedule for a team, including pitcher info."""
    return jsonify(schedule_service.get_schedule_for_team(team_id))

@schedule_bp.route('/next_schedule/<int:team_id>', methods=['GET'])
@lru_cache(maxsize=128)
def get_next_schedule_route(team_id):
    """Gets the upcoming schedule (today or tomorrow) for a team."""
    return jsonify(schedule_service.get_next_game_schedule_for_team(team_id))

@schedule_bp.route('/team-stats/<int:team_id>/<int:num_games>', methods=['GET'])
async def get_stats_batch_route(team_id: int, num_games: int):
    """Gets a summary of team stats (NRFI, F5, Win%) over the last N completed games."""
    stats_summary = await game_service.get_team_stats_summary(team_id, num_games, include_details=True)

    if isinstance(stats_summary, dict) and stats_summary.get("error"):
        return jsonify(stats_summary), 500
        
    return jsonify(stats_summary) 