import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Iterable, Iterator, Optional, Tuple

FIELD_SEP = "÷"
ROW_SEP = "¬"
TEAM_SUFFIX_RE = re.compile(r"\s\(...\)")

FLASHSCORE_HOST = "www.flashscorekz.com"
FLASHSCORE_BASE = f"https://{FLASHSCORE_HOST}/"
FLASHSCORE_SOURCER = f"{FLASHSCORE_HOST}/"
DEFAULT_FEED_SUFFIX = "_ru_1"

# Без нормального UA flashscorekz иногда рвёт TLS (WinError 10054).
API_HEADERS = {
    "X-Fsign": "SW9D1eZo",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def map_source(source_value) -> Tuple[str, str]:
    """Всегда flashscorekz.com (источник X2 сохранён для совместимости с Excel)."""
    _ = source_value
    return FLASHSCORE_SOURCER, DEFAULT_FEED_SUFFIX


def map_odds_params(source_value) -> list:
    """API pq_graphql: projectId + geo для источника из Старт!X2."""
    try:
        source = str(int(float(source_value)))
    except (TypeError, ValueError):
        source = str(source_value or "").strip()

    if source == "1":
        return [("46", "KE", "KE30"), ("1", "SE", "SEAB")]
    if source == "2":
        return [("46", "KZ", "KZALM"), ("46", "US", "USNY"), ("1", "SE", "SEAB")]
    if source == "5":
        return [("46", "UA", "UA30"), ("1", "SE", "SEAB")]
    if source == "4":
        return [("1", "SE", "SEAB"), ("46", "KZ", "KZALM")]
    return [("46", "KZ", "KZALM"), ("1", "SE", "SEAB")]


def match_list_feed_url(
    sport_id: int,
    dayzone: int,
    timezone: int,
    *,
    sourcer: str = FLASHSCORE_SOURCER,
    suffix: str = DEFAULT_FEED_SUFFIX,
) -> str:
    return f"https://{sourcer}x/feed/f_{int(sport_id)}_{dayzone}_{timezone}{suffix}"


def match_detail_feed_url(
    sport_id: int,
    match_id: str,
    *,
    sourcer: str = FLASHSCORE_SOURCER,
) -> str:
    return f"https://{sourcer}x/feed/dc_{int(sport_id)}_{match_id}"


def odds_list_feed_url(
    sport_id: int,
    dayzone: int,
    timezone: int,
    *,
    sourcer: str = FLASHSCORE_SOURCER,
    suffix: str = DEFAULT_FEED_SUFFIX,
) -> str:
    return f"https://{sourcer}x/feed/fo_{int(sport_id)}_{dayzone}_{timezone}{suffix}0"


def _feed_fallback_urls(url: str) -> list[str]:
    """Повторы только на том же хосте (flashscorekz.com)."""
    return [url]


def fetch_feed(url: str, *, retries: int = 4, timeout: int = 30) -> str:
    """GET x/feed с retry на flashscorekz.com."""
    last_err: Optional[BaseException] = None
    for candidate in _feed_fallback_urls(url):
        headers = dict(API_HEADERS)
        host = candidate.split("/")[2] if "://" in candidate else FLASHSCORE_HOST
        if host:
            headers["Referer"] = f"https://{host}/"
        for attempt in range(max(1, retries)):
            try:
                req = urllib.request.Request(candidate, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                last_err = exc
                code = getattr(exc, "code", None)
                if code in (404, 410, 403):
                    print(f"[!] feed {candidate}: HTTP {code}")
                    break
                print(f"[!] feed retry {attempt + 1}/{retries} {candidate}: {exc}")
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"fetch_feed failed for {url}: {last_err}") from last_err


def iter_feed_rows(text: str) -> Iterator[Tuple[str, str, list]]:
    for row in text.split("~"):
        if not row:
            continue
        fields = row.split(ROW_SEP)
        if not fields:
            continue
        first = fields[0].split(FIELD_SEP)
        if len(first) < 2:
            continue
        yield first[0], first[1], fields


def parse_fields(fields: Iterable[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for field in fields:
        parts = field.split(FIELD_SEP)
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def clean_team_name(name: str) -> str:
    return TEAM_SUFFIX_RE.sub("", name or "").strip()


def format_match_date(ts_value: str, timezone: int, time_offset: int) -> str:
    from date_utils import format_ts_match_date

    return format_ts_match_date(ts_value, timezone, time_offset)


def adjust_half_scores(home_first: int, away_first: int, home_second: int, away_second: int) -> Tuple[int, int]:
    return home_first - home_second, away_first - away_second
