import asyncio
import threading

import aiohttp

_sessions: dict[asyncio.AbstractEventLoop, aiohttp.ClientSession] = {}
_lock = threading.Lock()


def _build_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=20),
        timeout=aiohttp.ClientTimeout(total=10),
    )


def _pop_stale_sessions() -> list[aiohttp.ClientSession]:
    stale_sessions: list[aiohttp.ClientSession] = []
    with _lock:
        for loop, session in list(_sessions.items()):
            if session.closed or loop.is_closed():
                _sessions.pop(loop, None)
                if not session.closed:
                    stale_sessions.append(session)
    return stale_sessions


async def get_session() -> aiohttp.ClientSession:
    loop = asyncio.get_running_loop()

    stale_sessions = _pop_stale_sessions()
    for session in stale_sessions:
        await session.close()

    with _lock:
        session = _sessions.get(loop)
        if session is not None and not session.closed:
            return session

        session = _build_session()
        _sessions[loop] = session
        return session


async def close_all_sessions() -> None:
    with _lock:
        sessions = list(_sessions.values())
        _sessions.clear()

    for session in sessions:
        if not session.closed:
            await session.close()


def register_teardown(app):
    @app.teardown_appcontext
    def _close_aiohttp_session(exception=None):
        return None
