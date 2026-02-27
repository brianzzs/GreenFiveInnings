import os
from app import create_app

config_name = os.getenv('FLASK_CONFIG', 'dev') 
app = create_app(config_name)

if __name__ == '__main__':
    host = os.getenv('HOST', '::')
    port = int(os.getenv('PORT', '8000'))
    app.run(host=host, port=port) 
