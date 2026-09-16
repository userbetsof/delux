"""Погодный снимок Open-Meteo без сетевых запросов."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from weather import forecast_url, kickoff_utc, parse_hourly_weather, resolve_venue


HOURLY = {
    "hourly": {
        "time": ["2026-09-10T16:00", "2026-09-10T17:00", "2026-09-10T18:00"],
        "temperature_2m": [14.0, 13.2, 12.4],
        "apparent_temperature": [13.0, 12.1, 11.0],
        "precipitation": [0.0, 0.4, 1.1],
        "precipitation_probability": [10, 45, 80],
        "snowfall": [0.0, 0.0, 0.0],
        "cloud_cover": [20, 65, 90],
        "relative_humidity_2m": [55, 70, 81],
        "wind_speed_10m": [2.0, 3.4, 4.6],
        "wind_gusts_10m": [4.0, 7.2, 9.1],
        "weather_code": [1, 61, 63],
    }
}


class TestWeather(TestCase):
    def test_kickoff_prefers_unix_timestamp(self):
        result = kickoff_utc(1789063200, "2020.01.01 00:00")
        self.assertEqual(result, datetime.fromtimestamp(1789063200, tz=timezone.utc))

    def test_kickoff_fallback_uses_local_offset(self):
        result = kickoff_utc(None, "2026.09.10 20:00", local_utc_offset=3)
        self.assertEqual(result.isoformat(), "2026-09-10T17:00:00+00:00")

    def test_selects_nearest_hour_and_metadata(self):
        target = datetime(2026, 9, 10, 17, 20, tzinfo=timezone.utc)
        fetched = datetime(2026, 9, 9, 17, 20, tzinfo=timezone.utc)
        data = parse_hourly_weather(HOURLY, target, fetched_at=fetched)
        self.assertEqual(data["weather_at"], "2026-09-10T17:00:00Z")
        self.assertEqual(data["temperature_c"], 13.2)
        self.assertEqual(data["wind_ms"], 3.4)
        self.assertEqual(data["precipitation_probability"], 45)
        self.assertEqual(data["lead_hours"], 24.0)
        self.assertEqual(data["kind"], "forecast")

    def test_empty_hourly(self):
        self.assertEqual(
            parse_hourly_weather({}, datetime(2026, 9, 10, tzinfo=timezone.utc)),
            {},
        )

    def test_forecast_url_is_utc_and_ms(self):
        url = forecast_url(48.13743, 11.57549, datetime(2026, 9, 10, tzinfo=timezone.utc))
        self.assertIn("timezone=UTC", url)
        self.assertIn("wind_speed_unit=ms", url)
        self.assertIn("start_date=2026-09-10", url)

    @patch("db.upsert_venue")
    @patch("db.get_cached_venue", return_value=None)
    @patch(
        "weather._get_json",
        return_value={"results": [{"latitude": 48.137, "longitude": 11.575, "timezone": "Europe/Berlin"}]},
    )
    def test_venue_geocoding_is_cached(self, get_json, _get_cached, upsert):
        location = resolve_venue("Альянц Арена", "Мюнхен")
        self.assertEqual(location["latitude"], 48.137)
        self.assertEqual(location["longitude"], 11.575)
        self.assertIn("name=", get_json.call_args.args[0])
        upsert.assert_called_once()
