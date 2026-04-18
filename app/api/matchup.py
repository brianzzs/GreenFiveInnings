from flask import Blueprint, jsonify
from app.services import matchup_service

matchup_bp = Blueprint("matchup", __name__, url_prefix="/best-matchups")


@matchup_bp.route("/today", methods=["GET"])
async def get_best_matchups_today():
    """Returns best batter-vs-pitcher matchups across today's games."""
    return jsonify(await matchup_service.get_best_matchups())
