import asyncio
import threading

import aiohttp

_loop_sessions: dict[int, aiohttp.ClientSession] = {}
_lock = threading.Lock()


def _create_connector() -> aiohttp.TCPConnector:
    return aiohttp.TCPConnector(limit=20)


async def get_session() -> aiohttp.ClientSession:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    loop_id = id(loop)
    with _lock:
        session = _loop_sessions.get(loop_id)
        if session is None or session.closed:
            session = aiohttp.ClientSession(
                connector=_create_connector(),
                timeout=aiohttp.ClientTimeout(total=10),
            )
            _loop_sessions[loop_id] = session
    return session


async def close_all_sessions() -> None:
    with _lock:
        for loop_id in list(_loop_sessions):
            session = _loop_sessions.pop(loop_id, None)
            if session and not session.closed:
                await session.close()


def _cleanup_dead_sessions() -> None:
    with _lock:
        dead_keys = [k for k, s in _loop_sessions.items() if s.closed]
        for k in dead_keys:
            _loop_sessions.pop(k, None)


def register_teardown(app):
    @app.teardown_appcontext
    def _close_aiohttp_session(exception=None):
        _cleanup_dead_sessions()
