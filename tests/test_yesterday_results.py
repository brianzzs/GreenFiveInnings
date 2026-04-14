import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, patch

from app import create_app
from app.services import schedule_service
from cache import _ttl_cache


def _standings_payload():
    return {
        200: {
            "teams": [
                {"team_id": 110, "w": 2, "l": 1},
                {"team_id": 111, "w": 3, "l": 0},
                {"team_id": 112, "w": 1, "l": 2},
                {"team_id": 142, "w": 1, "l": 2},
            ]
        }
    }


class YesterdayResultsServiceTests(unittest.TestCase):
    def setUp(self):
        _ttl_cache.clear()

    def tearDown(self):
        _ttl_cache.clear()

    @patch("app.services.schedule_service.season_context.reference_date")
    @patch(
        "app.services.schedule_service.mlb_stats_client.get_standings",
        new_callable=AsyncMock,
    )
    @patch("app.services.schedule_service.mlb_stats_client.get_schedule")
    def test_get_yesterday_results_returns_completed_games_sorted_and_shaped(
        self,
        mock_get_schedule,
        mock_get_standings,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 3, 30)
        mock_get_standings.return_value = _standings_payload()
        mock_get_schedule.return_value = [
            {
                "game_id": 2,
                "game_date": "2026-03-29",
                "game_datetime": "2026-03-29T21:10:00Z",
                "status": "Final",
                "away_id": 112,
                "away_name": "CHC Cubs",
                "away_score": 4,
                "home_id": 111,
                "home_name": "BOS Red Sox",
                "home_score": 5,
            },
            {
                "game_id": 3,
                "game_date": "2026-03-29",
                "game_datetime": "2026-03-29T19:10:00Z",
                "status": "In Progress",
                "away_id": 110,
                "away_name": "BAL Orioles",
                "away_score": 1,
                "home_id": 142,
                "home_name": "MIN Twins",
                "home_score": 2,
            },
            {
                "game_id": 1,
                "game_date": "2026-03-29",
                "game_datetime": "2026-03-29T17:35:00Z",
                "status": "Game Over",
                "away_id": 142,
                "away_name": "MIN Twins",
                "away_score": 6,
                "home_id": 110,
                "home_name": "BAL Orioles",
                "home_score": 8,
            },
        ]

        results = asyncio.run(schedule_service.get_yesterday_results())

        self.assertEqual([game["game_id"] for game in results], [2, 1])
        self.assertEqual(results[1]["away_team"]["record"], "1-2")
        self.assertEqual(results[1]["home_team"]["record"], "2-1")
        self.assertEqual(
            results[1]["away_team"]["logo_url"],
            "https://www.mlbstatic.com/team-logos/142.svg",
        )
        self.assertEqual(results[1]["away_team"]["runs"], 6)
        self.assertEqual(results[1]["home_team"]["runs"], 8)
        self.assertEqual(results[0]["home_team"]["name"], "BOS Red Sox")
        self.assertEqual(results[0]["status"], "Final")

    @patch("app.services.schedule_service.season_context.reference_date")
    @patch(
        "app.services.schedule_service.mlb_stats_client.get_standings",
        new_callable=AsyncMock,
    )
    @patch("app.services.schedule_service.mlb_stats_client.get_schedule")
    def test_get_yesterday_results_uses_yesterday_for_standings_lookup(
        self,
        mock_get_schedule,
        mock_get_standings,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 3, 30)
        mock_get_standings.return_value = _standings_payload()
        mock_get_schedule.return_value = []

        asyncio.run(schedule_service.get_yesterday_results())

        self.assertEqual(mock_get_standings.call_args.kwargs["date"], "2026-03-29")

    @patch("app.services.schedule_service.season_context.reference_date")
    @patch(
        "app.services.schedule_service.mlb_stats_client.get_standings",
        new_callable=AsyncMock,
    )
    @patch("app.services.schedule_service.mlb_stats_client.get_schedule")
    def test_get_yesterday_results_returns_empty_list_when_no_games(
        self,
        mock_get_schedule,
        mock_get_standings,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 3, 30)
        mock_get_standings.return_value = _standings_payload()
        mock_get_schedule.return_value = []

        self.assertEqual(asyncio.run(schedule_service.get_yesterday_results()), [])

    @patch("app.services.schedule_service.season_context.reference_date")
    @patch(
        "app.services.schedule_service.mlb_stats_client.get_standings",
        new_callable=AsyncMock,
    )
    @patch("app.services.schedule_service.mlb_stats_client.get_schedule")
    def test_get_recent_results_groups_today_and_yesterday(
        self,
        mock_get_schedule,
        mock_get_standings,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 3, 30)
        mock_get_standings.return_value = _standings_payload()
        mock_get_schedule.side_effect = [
            [
                {
                    "game_id": 10,
                    "game_date": "2026-03-30",
                    "game_datetime": "2026-03-30T20:10:00Z",
                    "status": "Final",
                    "away_id": 112,
                    "away_name": "CHC Cubs",
                    "away_score": 3,
                    "home_id": 111,
                    "home_name": "BOS Red Sox",
                    "home_score": 4,
                }
            ],
            [
                {
                    "game_id": 1,
                    "game_date": "2026-03-29",
                    "game_datetime": "2026-03-29T17:35:00Z",
                    "status": "Final",
                    "away_id": 142,
                    "away_name": "MIN Twins",
                    "away_score": 6,
                    "home_id": 110,
                    "home_name": "BAL Orioles",
                    "home_score": 8,
                }
            ],
        ]

        results = asyncio.run(schedule_service.get_recent_results())

        self.assertEqual([game["game_id"] for game in results["today"]], [10])
        self.assertEqual([game["game_id"] for game in results["yesterday"]], [1])
        self.assertEqual(
            mock_get_standings.call_args_list[0].kwargs["date"], "2026-03-30"
        )
        self.assertEqual(
            mock_get_standings.call_args_list[1].kwargs["date"], "2026-03-29"
        )


class RecentResultsRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("test")
        self.client = self.app.test_client()

    @patch(
        "app.api.schedule.schedule_service.get_recent_results",
        new_callable=AsyncMock,
    )
    def test_recent_results_route_returns_json(self, mock_get_recent_results):
        mock_get_recent_results.return_value = {
            "today": [
                {
                    "game_id": 824900,
                    "game_date": "2026-03-30",
                    "game_datetime": "2026-03-30T17:35:00Z",
                    "status": "Final",
                    "away_team": {
                        "id": 112,
                        "name": "Chicago Cubs",
                        "record": "1-2",
                        "logo_url": "https://www.mlbstatic.com/team-logos/112.svg",
                        "runs": 3,
                    },
                    "home_team": {
                        "id": 111,
                        "name": "Boston Red Sox",
                        "record": "3-0",
                        "logo_url": "https://www.mlbstatic.com/team-logos/111.svg",
                        "runs": 4,
                    },
                }
            ],
            "yesterday": [
                {
                    "game_id": 824864,
                    "game_date": "2026-03-29",
                    "game_datetime": "2026-03-29T17:35:00Z",
                    "status": "Final",
                    "away_team": {
                        "id": 142,
                        "name": "Minnesota Twins",
                        "record": "1-2",
                        "logo_url": "https://www.mlbstatic.com/team-logos/142.svg",
                        "runs": 6,
                    },
                    "home_team": {
                        "id": 110,
                        "name": "Baltimore Orioles",
                        "record": "2-1",
                        "logo_url": "https://www.mlbstatic.com/team-logos/110.svg",
                        "runs": 8,
                    },
                }
            ],
        }

        response = self.client.get("/recent_results")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), mock_get_recent_results.return_value)


if __name__ == "__main__":
    unittest.main()
