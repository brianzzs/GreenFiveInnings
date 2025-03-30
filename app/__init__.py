from flask import Flask
from flask_cors import CORS
from .config import config_by_name
import os

from .api.schedule import schedule_bp
from .api.player import player_bp
from .api.teams import teams_bp

def create_app(config_name='default'): 
    """Flask application factory pattern."""
    app = Flask(__name__.split('.')[0]) 

    flask_config_name = os.getenv('FLASK_CONFIG') or config_name
    app.config.from_object(config_by_name[flask_config_name])

    CORS(app)

    app.register_blueprint(schedule_bp) 
    app.register_blueprint(player_bp) 
    app.register_blueprint(teams_bp) 

    @app.route('/')
    def index():
        return "API is running!" 
    return app
