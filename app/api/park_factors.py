from flask import Blueprint, jsonify

from app.services import park_factor_service

park_factors_bp = Blueprint("park_factors", __name__)


@park_factors_bp.route("/park-factors", methods=["GET"])
def park_factors_route():
    return jsonify(park_factor_service.get_today_park_factors())
