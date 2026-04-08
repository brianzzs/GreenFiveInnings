from flask import Blueprint, jsonify
from app.services import schedule_service

league_bp = Blueprint('league', __name__)


@league_bp.route('/mlb', methods=['GET'])
def get_standings():
   return schedule_service.get_standings()
