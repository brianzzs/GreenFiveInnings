import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, patch

from app.services import game_service, schedule_service
from cache import _ttl_cache


def _standings_payload():
    return {
        200: {
            "teams": [
                {"team_id": 111, "w": 10, "l": 8},
                {"team_id": 112, "w": 8, "l": 10},
                {"team_id": 142, "w": 9, "l": 9},
            ]
        }
    }


def _game_detail(game_id: int, game_date: str, game_datetime: str) -> dict:
    return {
        "gameData": {
            "game": {"pk": game_id},
            "datetime": {
                "originalDate": game_date,
                "dateTime": game_datetime,
            },
            "teams": {
                "away": {"id": 111},
                "home": {"id": 142},
            },
        },
        "liveData": {
            "linescore": {
                "innings": [
                    {
                        "away": {"runs": 0},
                        "home": {"runs": 1},
                    }
                ],
                "teams": {
                    "away": {"runs": 2},
                    "home": {"runs": 4},
                },
            }
        },
    }


class ScheduleOrderingTests(unittest.TestCase):
    def setUp(self):
        _ttl_cache.clear()

    def tearDown(self):
        _ttl_cache.clear()

    @patch("app.services.schedule_service.season_context.reference_date")
    @patch(
        "app.services.schedule_service.player_service.fetch_and_cache_pitcher_info",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.schedule_service.mlb_stats_client.get_standings",
        new_callable=AsyncMock,
    )
    @patch("app.services.schedule_service.mlb_stats_client.get_schedule")
    def test_get_schedule_for_team_returns_most_recent_first(
        self,
        mock_get_schedule,
        mock_get_standings,
        mock_fetch_pitcher_info,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 18)
        mock_get_standings.return_value = _standings_payload()
        mock_fetch_pitcher_info.return_value = {}
        mock_get_schedule.return_value = [
            {
                "game_id": 1,
                "home_id": 142,
                "home_name": "MIN Twins",
                "away_id": 111,
                "away_name": "BOS Red Sox",
                "status": "Final",
                "game_datetime": "2026-04-14T23:40:00Z",
            },
            {
                "game_id": 2,
                "home_id": 142,
                "home_name": "MIN Twins",
                "away_id": 111,
                "away_name": "CIN Reds",
                "status": "Final",
                "game_datetime": "2026-04-18T00:10:00Z",
            },
            {
                "game_id": 3,
                "home_id": 142,
                "home_name": "MIN Twins",
                "away_id": 111,
                "away_name": "BOS Red Sox",
                "status": "Final",
                "game_datetime": "2026-04-15T17:40:00Z",
            },
        ]

        results = asyncio.run(schedule_service.get_schedule_for_team(142, num_days=4))

        self.assertEqual([game["game_id"] for game in results], [2, 3, 1])


class TeamStatsOrderingTests(unittest.TestCase):
    @patch(
        "app.services.game_service.schedule_service.fetch_last_n_completed_game_ids",
        new_callable=AsyncMock,
    )
    @patch("app.services.game_service.fetch_game_details_batch", new_callable=AsyncMock)
    def test_team_stats_uses_most_recent_games_when_batch_is_out_of_order(
        self,
        mock_fetch_game_details_batch,
        mock_fetch_last_n_completed_game_ids,
    ):
        mock_fetch_last_n_completed_game_ids.return_value = [10, 20, 30]
        mock_fetch_game_details_batch.return_value = [
            _game_detail(10, "2026-04-14", "2026-04-14T23:40:00Z"),
            _game_detail(20, "2026-04-17", "2026-04-18T00:10:00Z"),
            _game_detail(30, "2026-04-15", "2026-04-15T17:40:00Z"),
        ]

        summary = asyncio.run(
            game_service.get_team_stats_full_gamesummary(
                142,
                2,
                include_details=True,
            )
        )

        self.assertEqual(summary["games_analyzed"], 2)
        self.assertEqual(
            [result["game_date"] for result in summary["results"]],
            ["2026-04-17", "2026-04-15"],
        )


if __name__ == "__main__":
    unittest.main()
