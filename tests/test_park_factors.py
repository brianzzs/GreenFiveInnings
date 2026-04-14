import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, patch

from app import create_app
from app.services import park_factor_service
from cache import _ttl_cache


def _forecast_payload(
    timezone: str,
    *,
    hourly_times: list[str],
    temperatures: list[float],
    wind_speeds: list[float],
    wind_gusts: list[float],
    wind_directions: list[float],
    precipitation_probabilities: list[float],
    humidities: list[float] | None = None,
    daily_date: str = "2026-04-10",
    temp_max_f: float = 75.0,
    temp_min_f: float = 55.0,
):
    return {
        "timezone": timezone,
        "hourly": [
            {
                "time": hourly_times[index],
                "temperature_f": temperatures[index],
                "wind_speed_mph": wind_speeds[index],
                "wind_gust_mph": wind_gusts[index],
                "wind_direction_degrees": wind_directions[index],
                "precipitation_probability_pct": precipitation_probabilities[index],
                "humidity_pct": (humidities[index] if humidities else 50),
            }
            for index in range(len(hourly_times))
        ],
        "daily": {
            daily_date: {
                "temp_max_f": temp_max_f,
                "temp_min_f": temp_min_f,
            }
        },
    }


class ParkFactorServiceTests(unittest.TestCase):
    def setUp(self):
        _ttl_cache.clear()

    def tearDown(self):
        _ttl_cache.clear()

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_get_today_park_factors_returns_card_payload_for_scheduled_and_in_progress_games(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 1,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T19:20:00Z",
                "away_id": 134,
                "away_name": "Pittsburgh Pirates",
                "home_id": 112,
                "home_name": "Chicago Cubs",
                "venue_name": "Wrigley Field",
            },
            {
                "game_id": 2,
                "status": "In Progress",
                "game_datetime": "2026-04-10T23:07:00Z",
                "away_id": 142,
                "away_name": "Minnesota Twins",
                "home_id": 141,
                "home_name": "Toronto Blue Jays",
                "venue_name": "Rogers Centre",
            },
            {
                "game_id": 3,
                "status": "Final",
                "game_datetime": "2026-04-10T17:05:00Z",
                "away_id": 110,
                "away_name": "Baltimore Orioles",
                "home_id": 111,
                "home_name": "Boston Red Sox",
                "venue_name": "Fenway Park",
            },
        ]
        mock_get_forecast.side_effect = [
            _forecast_payload(
                "America/Chicago",
                hourly_times=[
                    "2026-04-10T13:00",
                    "2026-04-10T14:00",
                    "2026-04-10T15:00",
                ],
                temperatures=[66, 72, 74],
                wind_speeds=[8, 12, 10],
                wind_gusts=[10, 17, 13],
                wind_directions=[225, 225, 225],
                precipitation_probabilities=[5, 5, 5],
                humidities=[45, 48, 50],
                daily_date="2026-04-10",
                temp_max_f=75,
                temp_min_f=58,
            ),
            _forecast_payload(
                "America/Toronto",
                hourly_times=["2026-04-10T18:00", "2026-04-10T19:00"],
                temperatures=[50, 49],
                wind_speeds=[16, 15],
                wind_gusts=[22, 21],
                wind_directions=[180, 180],
                precipitation_probabilities=[60, 60],
                humidities=[65, 63],
                daily_date="2026-04-10",
                temp_max_f=52,
                temp_min_f=45,
            ),
        ]

        payload = asyncio.run(park_factor_service.get_today_park_factors())

        self.assertEqual(payload["date"], "2026-04-10")
        self.assertEqual([game["game_id"] for game in payload["games"]], [1, 2])

        wrigley_game = payload["games"][0]
        self.assertEqual(wrigley_game["matchup_label"], "PIT @ CHC")
        self.assertEqual(wrigley_game["weather"]["game_temp_f"], 72)
        self.assertEqual(wrigley_game["weather"]["temp_max_f"], 75)
        self.assertEqual(wrigley_game["weather"]["temp_min_f"], 58)
        self.assertEqual(wrigley_game["weather"]["humidity_pct"], 48)
        self.assertEqual(wrigley_game["weather"]["wind_direction_label"], "out")
        self.assertGreater(wrigley_game["factors"]["combined_runs_pct"], 0)
        self.assertGreater(wrigley_game["factors"]["combined_hr_pct"], 0)
        self.assertIn("wind_out", wrigley_game["traits"])
        self.assertIn("combined_2b3b_pct", wrigley_game["factors"])
        self.assertIn("combined_1b_pct", wrigley_game["factors"])

        rogers_game = payload["games"][1]
        self.assertEqual(rogers_game["venue"]["roof_status_assumption"], "closed")
        self.assertIn("roof_closed_assumed", rogers_game["traits"])
        self.assertEqual(
            rogers_game["summary"],
            "With the roof likely closed, weather should have limited impact on this matchup.",
        )

        highlights = payload["highlights"]
        self.assertEqual(highlights["best_hitter_environment"]["game_id"], 1)
        self.assertEqual(highlights["warmest_game"]["game_id"], 1)
        self.assertEqual(highlights["windiest_game"]["game_id"], 2)

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_get_today_park_factors_falls_back_to_stadium_only_when_weather_fails(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 10,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T18:20:00Z",
                "away_id": 120,
                "away_name": "Washington Nationals",
                "home_id": 113,
                "home_name": "Cincinnati Reds",
                "venue_name": "Great American Ball Park",
            }
        ]
        mock_get_forecast.side_effect = RuntimeError("weather unavailable")

        payload = asyncio.run(park_factor_service.get_today_park_factors())

        self.assertEqual(len(payload["games"]), 1)
        game = payload["games"][0]
        self.assertIsNone(game["weather"]["game_temp_f"])
        self.assertIsNone(game["weather"]["humidity_pct"])
        self.assertEqual(game["factors"]["weather_runs_pct"], 0)
        self.assertEqual(game["factors"]["weather_hr_pct"], 0)
        self.assertEqual(game["factors"]["weather_2b3b_pct"], 0)
        self.assertEqual(game["factors"]["weather_1b_pct"], 0)
        self.assertIn("weather_unavailable", game["traits"])
        self.assertEqual(
            game["summary"],
            "Weather data unavailable; card is using stadium baseline only.",
        )

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_get_today_park_factors_uses_cache_for_repeat_calls(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 20,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T18:20:00Z",
                "away_id": 120,
                "away_name": "Washington Nationals",
                "home_id": 113,
                "home_name": "Cincinnati Reds",
                "venue_name": "Great American Ball Park",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/New_York",
            hourly_times=["2026-04-10T14:00"],
            temperatures=[71],
            wind_speeds=[7],
            wind_gusts=[10],
            wind_directions=[225],
            precipitation_probabilities=[0],
            humidities=[50],
            daily_date="2026-04-10",
            temp_max_f=74,
            temp_min_f=60,
        )

        first_payload = asyncio.run(park_factor_service.get_today_park_factors())
        second_payload = asyncio.run(park_factor_service.get_today_park_factors())

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(mock_get_schedule.call_count, 1)
        self.assertEqual(mock_get_forecast.call_count, 1)

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_wind_in_produces_negative_hr_and_2b3b_effects(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 100,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T19:20:00Z",
                "away_id": 134,
                "away_name": "Pittsburgh Pirates",
                "home_id": 112,
                "home_name": "Chicago Cubs",
                "venue_name": "Wrigley Field",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/Chicago",
            hourly_times=["2026-04-10T14:00"],
            temperatures=[45],
            wind_speeds=[18],
            wind_gusts=[25],
            wind_directions=[45],
            precipitation_probabilities=[10],
            humidities=[40],
            daily_date="2026-04-10",
            temp_max_f=48,
            temp_min_f=38,
        )

        payload = asyncio.run(park_factor_service.get_today_park_factors())
        game = payload["games"][0]

        self.assertLess(game["factors"]["weather_hr_pct"], 0)
        self.assertLess(game["factors"]["weather_2b3b_pct"], 0)
        self.assertLess(game["factors"]["combined_runs_pct"], 0)
        self.assertIn("wind_in", game["traits"])
        self.assertIn("cold", game["traits"])
        self.assertIn("wind_sensitive_park", game["traits"])

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_retractable_roof_dampening_near_zero_when_closed(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 200,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T23:07:00Z",
                "away_id": 142,
                "away_name": "Minnesota Twins",
                "home_id": 141,
                "home_name": "Toronto Blue Jays",
                "venue_name": "Rogers Centre",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/Toronto",
            hourly_times=["2026-04-10T19:00"],
            temperatures=[40],
            wind_speeds=[20],
            wind_gusts=[28],
            wind_directions=[180],
            precipitation_probabilities=[70],
            humidities=[70],
            daily_date="2026-04-10",
            temp_max_f=42,
            temp_min_f=35,
        )

        payload = asyncio.run(park_factor_service.get_today_park_factors())
        game = payload["games"][0]

        self.assertEqual(game["venue"]["roof_status_assumption"], "closed")
        self.assertIn("roof_closed_assumed", game["traits"])
        self.assertAlmostEqual(abs(game["factors"]["weather_runs_pct"]), 0, delta=2)
        self.assertAlmostEqual(abs(game["factors"]["weather_hr_pct"]), 0, delta=2)

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_high_humidity_suppresses_hr_carry(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 300,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T18:40:00Z",
                "away_id": 121,
                "away_name": "New York Mets",
                "home_id": 143,
                "home_name": "Philadelphia Phillies",
                "venue_name": "Citizens Bank Park",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/New_York",
            hourly_times=["2026-04-10T14:00"],
            temperatures=[70],
            wind_speeds=[3],
            wind_gusts=[4],
            wind_directions=[300],
            precipitation_probabilities=[0],
            humidities=[85],
            daily_date="2026-04-10",
            temp_max_f=72,
            temp_min_f=62,
        )

        payload = asyncio.run(park_factor_service.get_today_park_factors())
        game = payload["games"][0]

        self.assertEqual(game["weather"]["humidity_pct"], 85)
        self.assertLess(game["factors"]["weather_hr_pct"], 0)

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_scaled_precipitation_penalty_increases_with_probability(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 400,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T18:10:00Z",
                "away_id": 110,
                "away_name": "Baltimore Orioles",
                "home_id": 135,
                "home_name": "San Diego Padres",
                "venue_name": "Petco Park",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/Los_Angeles",
            hourly_times=["2026-04-10T11:00"],
            temperatures=[65],
            wind_speeds=[6],
            wind_gusts=[9],
            wind_directions=[270],
            precipitation_probabilities=[80],
            humidities=[70],
            daily_date="2026-04-10",
            temp_max_f=67,
            temp_min_f=58,
        )

        payload = asyncio.run(park_factor_service.get_today_park_factors())
        game = payload["games"][0]

        self.assertIn("rain_risk", game["traits"])
        self.assertLess(game["factors"]["weather_runs_pct"], 0)
        self.assertLess(game["factors"]["weather_hr_pct"], 0)

    @patch("app.services.park_factor_service.season_context.reference_date")
    @patch(
        "app.services.park_factor_service.weather_client.get_forecast_for_park",
        new_callable=AsyncMock,
    )
    @patch("app.services.park_factor_service.mlb_stats_client.get_schedule")
    def test_wind_gusts_amplify_wind_effect_beyond_speed_alone(
        self,
        mock_get_schedule,
        mock_get_forecast,
        mock_reference_date,
    ):
        mock_reference_date.return_value = datetime.date(2026, 4, 10)
        mock_get_schedule.return_value = [
            {
                "game_id": 500,
                "status": "Scheduled",
                "game_datetime": "2026-04-10T19:20:00Z",
                "away_id": 134,
                "away_name": "Pittsburgh Pirates",
                "home_id": 112,
                "home_name": "Chicago Cubs",
                "venue_name": "Wrigley Field",
            }
        ]
        mock_get_forecast.return_value = _forecast_payload(
            "America/Chicago",
            hourly_times=["2026-04-10T14:00"],
            temperatures=[72],
            wind_speeds=[10],
            wind_gusts=[22],
            wind_directions=[225],
            precipitation_probabilities=[5],
            humidities=[50],
            daily_date="2026-04-10",
            temp_max_f=75,
            temp_min_f=60,
        )

        payload = asyncio.run(park_factor_service.get_today_park_factors())
        game = payload["games"][0]

        self.assertEqual(game["factors"]["stadium_hr_pct"], 1)
        self.assertGreater(game["factors"]["weather_hr_pct"], 0)
        self.assertGreater(game["factors"]["weather_2b3b_pct"], 0)
        self.assertIn("wind_out", game["traits"])


class ParkFactorsRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("test")
        self.client = self.app.test_client()

    @patch(
        "app.api.park_factors.park_factor_service.get_today_park_factors",
        new_callable=AsyncMock,
    )
    def test_park_factors_route_returns_json(self, mock_get_today_park_factors):
        mock_get_today_park_factors.return_value = {
            "date": "2026-04-10",
            "generated_at": "2026-04-10T18:05:00Z",
            "highlights": {},
            "games": [],
        }

        response = self.client.get("/park-factors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), mock_get_today_park_factors.return_value)


if __name__ == "__main__":
    unittest.main()
