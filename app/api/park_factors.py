from flask import Blueprint, jsonify

from app.services import park_factor_service

park_factors_bp = Blueprint("park_factors", __name__)


@park_factors_bp.route("/park-factors", methods=["GET"])
async def park_factors_route():
    return jsonify(await park_factor_service.get_today_park_factors())
