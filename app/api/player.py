from flask import Blueprint, jsonify
from app.services import player_service

player_bp = Blueprint('player', __name__, url_prefix='/player')

@player_bp.route('/search/<string:name>', methods=['GET'])
def search_player_route(name):
    """Searches for players by name."""
    return jsonify(player_service.search_player_by_name(name))

@player_bp.route('/stats/<int:player_id>/<string:season>', methods=['GET'])
def get_player_route(player_id, season):
    """Gets player stats for a given season."""
    return jsonify(player_service.get_player_stats(player_id, season))

@player_bp.route('/recent-stats/<int:player_id>/<int:num_games>', methods=['GET'])
async def get_recent_player_stats_route(player_id, num_games):
    """Gets recent game stats for a player."""
    stats = await player_service.get_player_recent_stats(player_id, num_games)
    return jsonify(stats)

@player_bp.route('/betting-stats/<int:player_id>/<int:num_games>', methods=['GET'])
async def get_player_betting_stats_route(player_id, num_games):
    """Gets player stats with betting market analysis."""
    stats = await player_service.get_player_betting_stats(player_id, num_games)
    return jsonify(stats)
