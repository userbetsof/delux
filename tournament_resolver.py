"""Резолвер tournament_key + season_id для прошедшего матча.

Цепочка (по match_id):
1. HTML страницы матча (/match/{id}/):
   - pageinfo: stage, tournament, tournamentTemplateId
   - header.tournament.link — URL лиги (слаг без сезона)
2. Страница лиги ({link}results/):
   - season_list: [{id, name, pathname}], где pathname=/standings/{tournament}/{stage}/
   - находим сезон по совпадению pathname со stage → name ("2015/2016")
3. Страница результатов сезона ({link-slug}-{name с '-'}/results/):
   - cjs.initialFeeds['results'] -> seasonId (числовой)

Всё сводится к (tournament_key=templateId, season_id=числовой), которые нужны
для tr_ feed URL: tr_{sport}_{country}_{tournament_key}_{season_id}_{page}.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from flashscore_feed import API_HEADERS

HOST = "www.flashscore.com"

# Кеш найденных ключей лиг: (sport, league_slug, country_slug) -> (ZEE, ZB).
_LEAGUE_KEYS_CACHE: Dict[Tuple[int, str, str], Tuple[str, str]] = {}


def _fetch(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={**dict(API_HEADERS), "Referer": "https://www.flashscore.com/"},
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", "replace")


def _match_page_data(match_id: str) -> Dict[str, str]:
    """Достать pageinfo + link лиги из HTML матча."""
    html = _fetch(f"https://{HOST}/match/{match_id}/")
    out: Dict[str, str] = {}

    m = re.search(r"pageinfo\s*=\s*(\{.*?\});", html, re.S)
    if m:
        try:
            pageinfo = json.loads(m.group(1))
        except json.JSONDecodeError:
            pageinfo = {}
        out["stage"] = pageinfo.get("stage", "")
        out["tournament"] = pageinfo.get("tournament", "")
        out["tournamentTemplateId"] = pageinfo.get("tournamentTemplateId", "")

    # слаг/ссылка лиги — из header.tournament.link.
    # В HTML слэши экранированы: "link":"\/football\/england\/premier-league\/".
    # Ищем "link":"...football..." до закрывающей кавычки, затем чистим обратные слэши.
    m = re.search(r'"link":"([^"]*?football[^"]*?)"', html)
    if m:
        link = m.group(1).replace("\\/", "/").replace("\\", "")
        out["league_link"] = link.rstrip("/") + "/"
    return out


def _season_name_from_stage(league_link: str, stage: str) -> str:
    """Найти name сезона ("2015/2016") по stage из season_list страницы лиги."""
    html = _fetch(f"https://{HOST}{league_link}results/")
    # season_list — массив объектов с pathname=/standings/{tournament}/{stage}/
    needle = f"/standings/*/{stage}/"
    # ищем объект с этим stage в pathname
    m = re.search(
        r'\{"id":\d+,"name":"([^"]+)","pathname":"\\?/standings\\?/[^"]*\\?/' + re.escape(stage) + r'\\?/"\}',
        html,
    )
    if m:
        return m.group(1)
    # fallback: перебрать season_list целиком
    m = re.search(r'"season_list":(\[.*?\])', html)
    if m:
        try:
            arr = json.loads(m.group(1))
        except json.JSONDecodeError:
            arr = []
        for item in arr:
            if stage in item.get("pathname", ""):
                return item.get("name", "")
    return ""


def _season_id_from_results(season_slug: str) -> str:
    """Достать seasonId из cjs.initialFeeds['results'] страницы результатов сезона."""
    html = _fetch(f"https://{HOST}{season_slug}results/")
    m = re.search(r"seasonId:\s*(\d+)", html)
    return m.group(1) if m else ""


def resolve_tournament_keys(match_id: str) -> Tuple[str, str, str]:
    """Резолв (tournament_key, season_id, league_link) из страницы матча.

    Возвращает (tournament_template_id, season_id, league_link).
    Пустые строки — если что-то не удалось.

    Если HTML-страница Flashscore недоступна (провайдер режет TLS-хендшейк),
    tournament_key/league_link берутся из pr_/tr_ фидов, а season_id — из
    сезонов, известных в локальной БД для этого турнира.
    """
    try:
        d = _match_page_data(match_id)
    except Exception:  # noqa: BLE001
        d = {}

    template = d.get("tournamentTemplateId", "")
    stage = d.get("stage", "")
    league_link = d.get("league_link", "")

    # Фолбэк: заголовок лиги из фидов (ZEE/ZB/ZL).
    if not template or not league_link:
        try:
            from feed_ids import resolve_match_ids_from_feed

            feed = resolve_match_ids_from_feed(match_id)
        except Exception:  # noqa: BLE001
            feed = {}
        if feed:
            template = template or feed.get("tournament_key", "")
            league_link = league_link or feed.get("league_link", "")

    season_id = ""
    if stage and league_link:
        name = _season_name_from_stage(league_link, stage)
        if name:
            name = name.replace("\\/", "/").replace("\\", "")
            # name "2015/2016" -> слаг лиги + "-2015-2016"
            season_suffix = name.replace("/", "-")
            slug = league_link.rstrip("/").split("/")[-1]
            country = league_link.strip("/").split("/")[1]
            season_slug = f"/football/{country}/{slug}-{season_suffix}/"
            season_id = _season_id_from_results(season_slug)

    # Фолбэк: сезон из БД по известным сезонам турнира (тот, где есть матч).
    if not season_id:
        season_id = _season_id_from_db(match_id, template)

    return template, season_id, league_link


def _season_id_from_db(match_id: str, tournament_key: str) -> str:
    return _probe_season_ids(match_id, tournament_key) if tournament_key else ""


def _known_season_ids(tournament_key: str) -> List[int]:
    """Сезоны-кандидаты для проверки через tr_.

    seasonId публикуется только в HTML страницы результатов лиги, поэтому при
    недоступной странице его приходится определять опытным путём: tr_ принимает
    season_id и отдаёт матчи сезона. Диапазон эмпирический (id у Flashscore
    нелинейны: 160=2014/15, 165=2015/16, 190=2025/26 для АПЛ).
    """
    return [
        190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180,
        179, 178, 177, 176, 175, 174, 173, 172, 171, 170, 169,
        168, 167, 166, 165, 164, 163, 162, 161, 160,
    ]


def _probe_season_ids(
    match_id: str, tournament_key: str, *, sport: int = 1, country: int = 198
) -> str:
    """Найти season_id: в чьём tr_ встречается этот матч.

    Проверяем сезоны по очереди и первые страницы каждого: нужный обычно
    находится на 3-8-й странице.
    """
    from flashscore_feed import fetch_feed

    for season_id in _known_season_ids(tournament_key):
        for page in range(12):
            url = (
                f"https://46.flashscore.ninja/46/x/feed/"
                f"tr_{sport}_{country}_{tournament_key}_{season_id}_{page}_1_ru-kz_1"
            )
            try:
                text = fetch_feed(url, retries=1, timeout=20)
            except Exception:  # noqa: BLE001
                break
            if not text or len(text) < 500:
                break
            if match_id in text:
                return str(season_id)
    return ""


def resolve_season_id(
    tournament_template_id: str,
    sport: int,
    country: int,
    kickoff_ts: int,
    match_id: str = "",
) -> Optional[str]:
    """Найти season_id через страницы Flashscore (pageinfo -> season_list -> results)."""
    if not match_id:
        return None
    _, season_id, _ = resolve_tournament_keys(match_id)
    return season_id or None


def resolve_season_from_url(url: str) -> Dict[str, Any]:
    """Из URL сезона (напр. .../football/england/premier-league-2015-2016/)
    достать (country_id, tournament_key, season_id, sport, league_slug).

    Читает cjs.initialFeeds['results'] страницы `/results/` и возвращает:
    {
        country_id, tournament_key (ZEE), season_id, sport, league_slug,
        sport_name ('football'|...), country_slug, season_label ('2015-2016'),
    }
    """
    url = (url or "").strip()
    if not url:
        return {}

    # нормализуем: оставляем путь /football/{country}/{league-slug}/
    path = url.split("?")[0].split("#")[0].rstrip("/")
    parts = [p for p in path.split("/") if p]
    # ищем 'football'/'soccer'/... в пути
    sport_name = ""
    sport = 1
    try:
        sport_idx = next(i for i, p in enumerate(parts) if p.lower() in ("football", "soccer", "baseball", "basketball", "hockey"))
    except StopIteration:
        return {}
    sport_name = parts[sport_idx].lower()
    sport = {"football": 1, "soccer": 1, "baseball": 6, "basketball": 3, "hockey": 4}.get(sport_name, 1)

    country_slug = parts[sport_idx + 1] if len(parts) > sport_idx + 1 else ""
    league_slug = ""
    season_label = ""
    if len(parts) > sport_idx + 2:
        raw = parts[sport_idx + 2]
        # raw может быть "premier-league-2015-2016"
        m = re.search(r"^(.*?)-(\d{4}-\d{4})$", raw)
        if m:
            league_slug = m.group(1)
            season_label = m.group(2)
        else:
            league_slug = raw

    results_url = f"/football/{country_slug}/{league_slug}-{season_label}/results/"

    season_id = ""
    tournament_key = ""
    country_id = ""
    try:
        html = _fetch(f"https://{HOST}{results_url}")
    except Exception:  # noqa: BLE001
        html = ""

    if html:
        m = re.search(r"seasonId:\s*(\d+)", html)
        season_id = m.group(1) if m else ""
        m = re.search(r"data:\s*`([^`]*)`", html)
        if m:
            data = m.group(1)
            zm = re.search(r"ZEE÷(\w+)", data)
            tournament_key = zm.group(1) if zm else ""
            zm = re.search(r"ZB÷(\d+)", data)
            country_id = zm.group(1) if zm else ""

    # Страница лиги недоступна (провайдер режет TLS) — берём ключи из фидов.
    # tournament_key/country_id находятся через любой матч этой лиги в БД,
    # season_id — подбором по tr_-фиду (сверяем год сезона с датами матчей).
    if not tournament_key or not season_id:
        feed = _season_from_url_via_feeds(
            country_slug=country_slug,
            league_slug=league_slug,
            season_label=season_label,
            sport=sport,
        )
        tournament_key = tournament_key or feed.get("tournament_key", "")
        country_id = country_id or feed.get("country_id", "")
        season_id = season_id or feed.get("season_id", "")

    return {
        "country_id": country_id,
        "tournament_key": tournament_key,
        "season_id": season_id,
        "sport": sport,
        "sport_name": sport_name,
        "country_slug": country_slug,
        "league_slug": league_slug,
        "season_label": season_label,
        "results_url": results_url,
    }


def _season_year(season_label: str) -> Optional[int]:
    """'2015-2016' → 2015 (год начала сезона)."""
    m = re.search(r"(\d{4})", season_label or "")
    return int(m.group(1)) if m else None


def _tr_season_year(
    tournament_key: str, season_id: str, *, sport: int, country: int
) -> Optional[int]:
    """Год НАЧАЛА сезона по датам матчей в tr_-фиде.

    Сезон идёт с лета по лето, поэтому год начала = год июльской даты.
    Брать min(AD) нельзя: он отдаёт год, в котором сезон заканчивается
    (2015/16 и 2014/15 оба задевают 2015), и сезоны путаются.
    """
    from datetime import datetime, timezone

    from flashscore_feed import fetch_feed

    url = (
        f"https://46.flashscore.ninja/46/x/feed/"
        f"tr_{sport}_{country}_{tournament_key}_{season_id}_0_1_ru-kz_1"
    )
    try:
        text = fetch_feed(url, retries=1, timeout=25)
    except Exception:  # noqa: BLE001
        return None
    if not text or len(text) < 500:
        return None
    stamps = [int(x) for x in re.findall(r"AD÷(\d+)", text)]
    if not stamps:
        return None
    # Год начала: если самая ранняя дата в июле..декабре — это и есть старт
    # сезона; если в январе..июне, то старт был в прошлом году.
    earliest = datetime.fromtimestamp(min(stamps), tz=timezone.utc)
    return earliest.year if earliest.month >= 7 else earliest.year - 1


def _fetch_league_keys_from_matches(
    *, sport: int, league_slug: str, country_slug: str, max_matches: int = 40
) -> Tuple[str, str]:
    """(tournament_key, country_id) — через pr_-фид любого матча этой лиги.

    Slug лиги ('premier-league') в БД не хранится (названия лиг кириллицей),
    зато pr_-фид матча содержит ZEE (ключ турнира), ZB (страну) и ZL (slug).
    Поэтому перебираем матчи и сверяем ZL со slug'ом из URL.

    Результат кешируется в памяти процесса: один и тот же сезон может
    резолвиться несколько раз за прогон.
    """
    cache_key = (sport, league_slug, country_slug)
    cached = _LEAGUE_KEYS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        from db import get_db_connection
    except Exception:  # noqa: BLE001
        return "", ""

    try:
        with get_db_connection() as conn:
            ids = [
                r[0]
                for r in conn.execute(
                    "SELECT match_id FROM matches "
                    "WHERE sport = ? AND match_status = 'Завершен' "
                    "ORDER BY start_ts DESC LIMIT ?",
                    (sport, max_matches),
                ).fetchall()
            ]
    except Exception:  # noqa: BLE001
        return "", ""

    from feed_ids import resolve_match_ids_from_feed

    for mid in ids:
        info = resolve_match_ids_from_feed(mid, sport=sport)
        if not info:
            continue
        link = (info.get("league_link") or "").rstrip("/")
        key = info.get("tournament_key", "")
        if not key or not link:
            continue
        # Сверяем и slug лиги, и страну из URL с тем, что вернул фид.
        if not link.endswith("/" + league_slug):
            continue
        if country_slug and f"/{country_slug}/" not in link:
            continue
        result = (key, info.get("country_id", ""))
        _LEAGUE_KEYS_CACHE[cache_key] = result
        return result
    return "", ""


def _season_from_url_via_feeds(
    *,
    country_slug: str,
    league_slug: str,
    season_label: str,
    sport: int,
) -> Dict[str, str]:
    """(tournament_key, country_id, season_id) без HTML-страницы."""
    target_year = _season_year(season_label)
    if not league_slug or target_year is None:
        return {}

    tournament_key, country_id = _fetch_league_keys_from_matches(
        sport=sport, league_slug=league_slug, country_slug=country_slug
    )
    if not tournament_key:
        return {}
    country = int(country_id) if country_id.isdigit() else 198
    print(f"    [feed] лига {league_slug}: tournament_key={tournament_key} country={country}")

    # seasonId в фидах не публикуется — перебираем и сверяем год по датам матчей.
    # Начинаем с сезонов рядом с целевым годом: id идут по возрастанию вместе
    # с годами, поэтому перебор от середины быстрее.
    candidates = _candidate_season_ids()
    # Эвристика: для АПЛ 165=2015/16, шаг ~1 сезон/год — начинаем с 160+(year-2010).
    guess = 160 + (target_year - 2010)
    candidates.sort(key=lambda sid: abs(sid - guess))
    for season_id in candidates:
        year = _tr_season_year(tournament_key, str(season_id), sport=sport, country=country)
        if year == target_year:
            print(f"    [feed] season_id={season_id} (год {year} совпал с {season_label})")
            return {
                "tournament_key": tournament_key,
                "country_id": str(country),
                "season_id": str(season_id),
            }
    print(f"    [!] сезон {season_label} не найден среди candidates")
    return {"tournament_key": tournament_key, "country_id": str(country)}


def _candidate_season_ids() -> List[int]:
    """Диапазон season_id Flashscore (нелинейны: 160=2014/15, 190=2025/26)."""
    return list(range(160, 196))
