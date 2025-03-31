from flask import Blueprint, jsonify, request
from app.services import comparison_service

comparison_bp = Blueprint('comparison', __name__, url_prefix='/comparison')

@comparison_bp.route('/<int:game_id>', methods=['GET'])
async def get_game_comparison_route(game_id):
    """Returns a comparison between the two teams playing in the specified game."""
    lookback_games = request.args.get('games', default=10, type=int)
    
    comparison_data = await comparison_service.get_game_comparison(
        game_id,
        lookback_games=lookback_games
    )
    
    if "error" in comparison_data:
        status_code = 500
        if "Could not fetch" in comparison_data.get("error", "") or "Missing team ID" in comparison_data.get("error", ""):
            status_code = 404
        return jsonify(comparison_data), status_code
        
    return jsonify(comparison_data) 