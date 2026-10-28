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

# Машинные фиды доступны и с edge-хостов .ninja, когда сайт заблокирован
# (TLS-хендшейк к flashscorekz.com не проходит). Путь после /x/feed/ один и
# тот же, поэтому меняется только хост.
FLASHSCORE_NINJA_HOST = "46.flashscore.ninja"
_USE_NINJA_FEED = False  # ставится в True после первого успешного переключения
# Пробуем основной хост всего один раз за процесс: если сайт заблокирован,
# нет смысла ждать 4 таймаута на каждом запросе.
_MAIN_HOST_DEAD = False


def feed_host_state() -> str:
    """Текущий хост фидов ('site' или 'ninja') — для логов."""
    return "ninja" if _USE_NINJA_FEED else "site"

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
    """Тот же URL, плюс запасной edge-хост .ninja (если сайт заблокирован).

    На .ninja путь содержит номер проекта: /46/x/feed/... — иначе 404.
    """
    urls = [url]
    if FLASHSCORE_HOST in url:
        alt = url.replace(FLASHSCORE_HOST, FLASHSCORE_NINJA_HOST)
        # /x/feed/ -> /46/x/feed/; двойной слэш схлопываем.
        alt = re.sub(r"/+x/feed/", "/46/x/feed/", alt)
        alt = re.sub(r"(?<!:)//+", "/", alt)
        if alt not in urls:
            urls.append(alt)
    return urls


def fetch_feed(url: str, *, retries: int = 4, timeout: int = 30) -> str:
    """GET x/feed с retry; при блокировке сайта — на edge-хосте .ninja."""
    global _USE_NINJA_FEED, _MAIN_HOST_DEAD

    last_err: Optional[BaseException] = None
    candidates = _feed_fallback_urls(url)
    # Если .ninja уже подтвердил работоспособность — начинаем сразу с него,
    # не тратя 4 таймаута на заблокированный хост.
    if _USE_NINJA_FEED and len(candidates) > 1:
        candidates = [candidates[1], candidates[0]]
    # Сайт уже признан мёртвым — основной хост даже не пробуем.
    elif _MAIN_HOST_DEAD and len(candidates) > 1:
        candidates = [candidates[1]]

    for index, candidate in enumerate(candidates):
        headers = dict(API_HEADERS)
        host = candidate.split("/")[2] if "://" in candidate else FLASHSCORE_HOST
        if host:
            headers["Referer"] = f"https://{host}/"
        on_ninja = FLASHSCORE_NINJA_HOST in candidate
        on_dead_main = _MAIN_HOST_DEAD and not on_ninja and len(candidates) > 1
        # Основной хост проверяем коротко: пока он не подтверждён живым,
        # хватит 2 попыток с урезанным таймаутом — иначе один заблокированный
        # сайт съедает больше минуты на старте.
        if on_ninja or on_dead_main:
            attempts = 1
            candidate_timeout = timeout
        elif not _USE_NINJA_FEED:
            attempts = min(2, max(1, retries))
            candidate_timeout = min(timeout, 8)
        else:
            attempts = max(1, retries)
            candidate_timeout = timeout
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(candidate, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=candidate_timeout) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                if on_ninja and not _USE_NINJA_FEED:
                    print(f"[*] фиды: переключаюсь на {FLASHSCORE_NINJA_HOST}")
                    _USE_NINJA_FEED = True
                    _MAIN_HOST_DEAD = True
                return body
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                last_err = exc
                code = getattr(exc, "code", None)
                if code in (404, 410, 403):
                    print(f"[!] feed {candidate}: HTTP {code}")
                    break
                # Временный сбой DNS (getaddrinfo failed) — повторяем, но не
                # помечаем хост мёртвым: он жив, проблема была в резолве.
                dns_error = "getaddrinfo" in str(exc).lower()
                if attempt + 1 < attempts:
                    print(f"[!] feed retry {attempt + 1}/{retries} {candidate}: {exc}")
                    time.sleep((0.6 if not dns_error else 1.2) * (attempt + 1))
        # Основной хост не ответил — помечаем мёртвым, остальные запросы
        # пойдут сразу на .ninja. Но не из-за разового сбоя DNS.
        if (
            not on_ninja
            and len(_feed_fallback_urls(url)) > 1
            and not (last_err and "getaddrinfo" in str(last_err).lower())
        ):
            _MAIN_HOST_DEAD = True
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
