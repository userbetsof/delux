"""Погодный снимок матча и история прогнозов Open-Meteo."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from date_utils import parse_match_datetime

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PROVIDER = "open-meteo"
HOURLY_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "snowfall",
    "cloud_cover",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
)
API_HEADERS = {
    "User-Agent": "DeluX/1.0 match-weather",
    "Accept": "application/json",
}


def _get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=API_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def kickoff_utc(
    start_ts: Optional[int] = None,
    date_match: str = "",
    *,
    local_utc_offset: int = 3,
) -> Optional[datetime]:
    """Исходный Unix timestamp, иначе локальная строка матча с известным смещением."""
    if start_ts:
        return datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
    local = parse_match_datetime(date_match)
    if local is None:
        return None
    local_zone = timezone(timedelta(hours=int(local_utc_offset)))
    return local.replace(tzinfo=local_zone).astimezone(timezone.utc)


def geocoding_url(town: str) -> str:
    query = urllib.parse.urlencode(
        {"name": town.strip(), "count": 5, "language": "ru", "format": "json"}
    )
    return f"{GEOCODING_URL}?{query}"


def resolve_venue(venue: str, town: str) -> Optional[Dict[str, Any]]:
    """Координаты арены: кэш по (venue, town), иначе геокодирование города."""
    venue = (venue or "").strip()
    town = (town or "").strip()
    if not town:
        return None

    from db import get_cached_venue, upsert_venue

    cached = get_cached_venue(venue, town)
    if cached:
        return dict(cached)

    payload = _get_json(geocoding_url(town))
    results = payload.get("results") or []
    if not results:
        return None
    exact = next(
        (item for item in results if str(item.get("name") or "").casefold() == town.casefold()),
        results[0],
    )
    data = {
        "latitude": float(exact["latitude"]),
        "longitude": float(exact["longitude"]),
        "timezone": exact.get("timezone"),
        "roof": False,
        "source": "open-meteo-geocoding",
    }
    upsert_venue(venue, town, data)
    return {"venue": venue, "town": town, **data}


def forecast_url(latitude: float, longitude: float, valid_at: datetime) -> str:
    day = valid_at.astimezone(timezone.utc).date().isoformat()
    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "hourly": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
            "start_date": day,
            "end_date": day,
        }
    )
    return f"{FORECAST_URL}?{query}"


def parse_hourly_weather(
    payload: Dict[str, Any],
    valid_at: datetime,
    *,
    fetched_at: Optional[datetime] = None,
    kind: str = "forecast",
) -> Dict[str, Any]:
    """Выбрать ближайший час из hourly-массива Open-Meteo."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return {}

    target = valid_at.astimezone(timezone.utc)
    parsed_times = [
        datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
        for value in times
    ]
    index = min(range(len(parsed_times)), key=lambda i: abs((parsed_times[i] - target).total_seconds()))
    selected = parsed_times[index]
    if abs((selected - target).total_seconds()) > 5400:
        return {}

    fetched = (fetched_at or datetime.now(timezone.utc)).astimezone(timezone.utc)

    def value(name: str):
        values = hourly.get(name) or []
        return values[index] if index < len(values) else None

    raw = {name: value(name) for name in HOURLY_FIELDS}
    return {
        "kind": kind,
        "valid_at": _utc_iso(target),
        "weather_at": _utc_iso(selected),
        "fetched_at": _utc_iso(fetched),
        "lead_hours": round((target - fetched).total_seconds() / 3600, 2),
        "temperature_c": value("temperature_2m"),
        "apparent_temperature_c": value("apparent_temperature"),
        "wind_ms": value("wind_speed_10m"),
        "gust_ms": value("wind_gusts_10m"),
        "precipitation_mm": value("precipitation"),
        "precipitation_probability": value("precipitation_probability"),
        "snowfall_cm": value("snowfall"),
        "cloud_pct": value("cloud_cover"),
        "humidity_pct": value("relative_humidity_2m"),
        "weather_code": value("weather_code"),
        "provider": PROVIDER,
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def fetch_weather(
    latitude: float,
    longitude: float,
    valid_at: datetime,
    *,
    kind: str = "forecast",
) -> Dict[str, Any]:
    payload = _get_json(forecast_url(latitude, longitude, valid_at))
    data = parse_hourly_weather(payload, valid_at, kind=kind)
    if data:
        data["latitude"] = latitude
        data["longitude"] = longitude
    return data


def save_weather_snapshot(
    match_id: str,
    *,
    venue: str,
    town: str,
    start_ts: Optional[int] = None,
    date_match: str = "",
    local_utc_offset: int = 3,
) -> Dict[str, Any]:
    """Получить прогноз, записать историю и погодный снимок текущего анализа."""
    valid_at = kickoff_utc(start_ts, date_match, local_utc_offset=local_utc_offset)
    location = resolve_venue(venue, town)
    if valid_at is None or location is None:
        return {}
    weather = fetch_weather(location["latitude"], location["longitude"], valid_at)
    if not weather:
        return {}
    weather.update(
        {
            "venue": venue,
            "town": town,
            "location_timezone": location.get("timezone"),
            "roof": bool(location.get("roof")),
        }
    )

    from db import insert_match_weather, upsert_match_snapshot

    insert_match_weather(match_id, weather)
    upsert_match_snapshot(
        match_id,
        {"weather_json": json.dumps(weather, ensure_ascii=False)},
    )
    return weather


def describe_weather(data: Dict[str, Any]) -> str:
    bits = []
    if data.get("temperature_c") is not None:
        bits.append(f"{data['temperature_c']} °C")
    if data.get("wind_ms") is not None:
        bits.append(f"ветер {data['wind_ms']} м/с")
    if data.get("precipitation_probability") is not None:
        bits.append(f"осадки {data['precipitation_probability']}%")
    if data.get("lead_hours") is not None:
        bits.append(f"за {data['lead_hours']} ч")
    return ", ".join(bits)
