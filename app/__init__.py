from flask import Flask, request, jsonify
from flask_cors import CORS

from app.api import league
from .config import config_by_name
import os
import secrets
import time
import functools
from typing import Optional
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .api.league import league_bp
from .api.schedule import schedule_bp
from .api.player import player_bp
from .api.teams import teams_bp
from .api.comparison import comparison_bp
from .api.park_factors import park_factors_bp
from .clients.http_session import register_teardown as register_aiohttp_teardown


def create_app(config_name="default"):
    """Flask application factory pattern."""
    app = Flask(__name__.split(".")[0])
    app.url_map.strict_slashes = False

    flask_config_name = os.getenv("FLASK_CONFIG") or config_name
    app.config.from_object(config_by_name[flask_config_name])

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["500 per day", "50 per hour"],
        storage_uri="memory://",
    )

    CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    "https://fiveinnings.com",
                    "http://localhost:3000",
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:3000",
                ],
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "X-API-Key", "Authorization"],
                "supports_credentials": True,
                "expose_headers": ["Content-Type", "X-API-Key", "Authorization"],
                "max_age": 3600,
            }
        },
    )

    def get_provided_api_key() -> Optional[str]:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key.strip()

        auth_header = request.headers.get("Authorization", "")
        bearer_prefix = "Bearer "
        if auth_header.startswith(bearer_prefix):
            return auth_header[len(bearer_prefix) :].strip()

        return None

    @app.before_request
    def authenticate():
        local_debug_addrs = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
        if app.config["DEBUG"] and request.remote_addr in local_debug_addrs:
            return None

        if request.method == "OPTIONS":
            return None

        if request.path == "/":
            return None

        if not app.config.get("API_KEY_REQUIRED", True):
            return None

        valid_api_key = os.environ.get("API_KEY")
        if not valid_api_key:
            app.logger.error(
                "API_KEY_REQUIRED is enabled but API_KEY is not configured."
            )
            return jsonify({"error": "Server authentication is not configured"}), 500

        provided_api_key = get_provided_api_key()
        if not provided_api_key or not secrets.compare_digest(
            provided_api_key, valid_api_key
        ):
            return jsonify({"error": "Unauthorized access"}), 401

        request.start_time = time.time()

    @app.after_request
    def add_security_headers(response):
        response.headers["Access-Control-Allow-Origin"] = request.headers.get(
            "Origin", "*"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-API-Key, Authorization"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        return response

    app.register_blueprint(schedule_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(comparison_bp)
    app.register_blueprint(park_factors_bp)
    app.register_blueprint(league_bp)
    register_aiohttp_teardown(app)

    @app.route("/")
    def index():
        return "API is running!"

    return app
