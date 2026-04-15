import os

from asgiref.wsgi import WsgiToAsgi

from app import create_app
from app.clients.http_session import close_all_sessions

config_name = os.getenv("FLASK_CONFIG", "prod")
flask_app = create_app(config_name)

_application = WsgiToAsgi(flask_app.wsgi_app)


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await close_all_sessions()
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await _application(scope, receive, send)
