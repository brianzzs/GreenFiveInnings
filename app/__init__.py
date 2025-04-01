from flask import Flask, request, jsonify
from flask_cors import CORS
from .config import config_by_name
import os
import time
import functools
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .api.schedule import schedule_bp
from .api.player import player_bp
from .api.teams import teams_bp
from .api.comparison import comparison_bp

def create_app(config_name='default'): 
    """Flask application factory pattern."""
    app = Flask(__name__.split('.')[0]) 

    flask_config_name = os.getenv('FLASK_CONFIG') or config_name
    app.config.from_object(config_by_name[flask_config_name])
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["500 per day", "50 per hour"],
        storage_uri="memory://",
    )
    
    CORS(app, resources={r"/*": {"origins": [
        "https://fiveinnings-api-f6d1667b55fe.herokuapp.com/", 
        "http://localhost:3000",            
        "http://localhost:5173",
        "https://fiveinnings.com/"

    ]}})
    
    @app.before_request
    def authenticate():
        if app.config['DEBUG'] and request.remote_addr == '127.0.0.1':
            return None
            
        if request.method == 'OPTIONS':
            return None
            
        if request.path == '/':
            return None
            
        api_key = request.headers.get('X-API-Key')
        valid_api_key = os.environ.get('API_KEY')
        
        if not api_key or api_key != valid_api_key:
            return jsonify({"error": "Unauthorized access"}), 401
            
        request.start_time = time.time()
    
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    
    app.register_blueprint(schedule_bp) 
    app.register_blueprint(player_bp) 
    app.register_blueprint(teams_bp) 
    app.register_blueprint(comparison_bp)

    @app.route('/')
    def index():
        return "API is running!" 
    
    return app
