import unittest

from app import create_app
from app.clients.http_session import get_session, close_all_sessions


class ASGIEntrypointTests(unittest.TestCase):
    def test_asgi_module_exposes_application_callable(self):
        import asgi

        self.assertTrue(callable(asgi.application))

    def test_asgi_module_creates_app_with_prod_config_by_default(self):
        import asgi

        self.assertIsNotNone(asgi.flask_app)

    def test_asgi_wraps_flask_wsgi_app(self):
        from asgiref.wsgi import WsgiToAsgi

        import asgi

        self.assertIsInstance(asgi._application, WsgiToAsgi)


class HttpSessionTests(unittest.TestCase):
    def test_get_session_returns_shared_singleton(self):
        import asyncio

        async def _run():
            session_a = await get_session()
            session_b = await get_session()
            self.assertIs(session_a, session_b)
            self.assertFalse(session_a.closed)
            await close_all_sessions()
            self.assertTrue(session_a.closed)

        asyncio.run(_run())

    def test_get_session_rotates_when_event_loop_changes(self):
        import asyncio

        async def _first_loop():
            return await get_session()

        first = asyncio.run(_first_loop())
        self.assertFalse(first.closed)

        async def _second_loop():
            second = await get_session()
            self.assertIsNot(first, second)
            self.assertTrue(first.closed)
            self.assertFalse(second.closed)
            await close_all_sessions()

        asyncio.run(_second_loop())

    def test_get_session_creates_new_after_close(self):
        import asyncio

        async def _run():
            first = await get_session()
            await close_all_sessions()
            self.assertTrue(first.closed)
            second = await get_session()
            self.assertIsNot(first, second)
            self.assertFalse(second.closed)
            await close_all_sessions()

        asyncio.run(_run())

    def test_close_all_sessions_idempotent(self):
        import asyncio

        async def _run():
            await get_session()
            await close_all_sessions()
            await close_all_sessions()

        asyncio.run(_run())


class ASGILifespanTests(unittest.TestCase):
    def test_lifespan_startup_and_shutdown(self):
        import asyncio

        async def _run():
            import asgi

            startup_sent = []
            shutdown_sent = []

            async def receive():
                if not startup_sent:
                    startup_sent.append(True)
                    return {"type": "lifespan.startup"}
                return {"type": "lifespan.shutdown"}

            async def send(message):
                pass

            await asgi.application({"type": "lifespan"}, receive, send)

        asyncio.run(_run())


class RoutePreservationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("test")
        self.client = self.app.test_client()

    def test_index_route_preserved(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"API is running", response.data)

    def test_schedule_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/today_schedule", rules)
        self.assertIn("/schedule/<int:team_id>", rules)

    def test_player_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/player/stats/<int:player_id>/<string:season>", rules)

    def test_teams_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/teams/<int:team_id>", rules)

    def test_comparison_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/comparison/<int:game_id>", rules)

    def test_park_factors_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/park-factors", rules)

    def test_league_route_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/mlb", rules)


if __name__ == "__main__":
    unittest.main()
