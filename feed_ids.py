"""Идентификаторы матча без HTML-страницы Flashscore.

Страница `/match/{id}/` у части провайдеров блокируется (TLS-хендшейк режется),
а машинные фиды `*.flashscore.ninja` доступны. Здесь те же данные берутся из фидов:

  pr_ (или df_hh) → ZEE (tournament key), ZB (country id), ZL (slug лиги)
                  → PX/PY в матче (participant keys команд)
  tr_             → тот же матч по турниру/сезону: PX/PY, ER (тур), AD (кикофф)

Что даёт HTML-страница и где взять:
  home/away participant id  → PX/PY из pr_/tr_
  tournamentTemplateId      → ZEE из заголовка ZA
  tournament (stage)        → stage из HTML; в фидах его нет (см. resolve_season_id_feed)
  league link               → ZL из заголовка ZA
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed, iter_feed_rows, parse_fields

FEED_HOST = "46.flashscore.ninja"
DEFAULT_COUNTRY = 198

# Записи фида разделены "¬~", поля — "¬" (ROW_SEP в flashscore_feed).
RECORD_SEP = ROW_SEP + "~"

# ZEE + ZB + ZL/ZA идут в одном блоке «лига» каждой страницы фида.
_LEAGUE_KEYS = ("ZA", "ZEE", "ZB", "ZL", "ZK", "ZY")


def feed_url(path: str) -> str:
    return f"https://{FEED_HOST}/46/x/feed/{path}"


def _records(text: str) -> List[Dict[str, str]]:
    """Разбить фид на блоки {поле: значение}."""
    out: List[Dict[str, str]] = []
    for chunk in (text or "").split(RECORD_SEP):
        if not chunk.strip():
            continue
        parsed = parse_fields([f for f in chunk.split(ROW_SEP) if f])
        if parsed:
            out.append(parsed)
    return out


def league_header(text: str) -> Dict[str, str]:
    """Заголовок лиги из фида: ZEE (tournament key), ZB (country), ZL (slug)."""
    for rec in _records(text):
        if any(k in rec for k in _LEAGUE_KEYS):
            return {k: rec.get(k, "") for k in _LEAGUE_KEYS}
    return {}


def match_from_team_feed(
    match_id: str,
    *,
    sport: int,
    country: int = DEFAULT_COUNTRY,
    team_key: str,
    max_pages: int = 40,
) -> Optional[Dict[str, str]]:
    """Найти матч в pr_-фиде команды и вернуть PX/PY и заголовок лиги."""
    if not team_key:
        return None
    country = country or DEFAULT_COUNTRY
    header: Dict[str, str] = {}
    for page in range(max_pages):
        url = feed_url(f"pr_{sport}_{country}_{team_key}_{page}_3_ru-kz_1")
        try:
            text = fetch_feed(url, retries=2, timeout=30)
        except Exception:  # noqa: BLE001
            return None
        if not text or len(text) < 2:
            return None
        head = league_header(text)
        if head and not header:
            header = head
        for rec in _records(text):
            if rec.get("AA") != match_id:
                continue
            return {
                "match_id": match_id,
                "home_id": rec.get("PX", ""),
                "away_id": rec.get("PY", ""),
                "home_name": rec.get("AE", ""),
                "away_name": rec.get("AF", ""),
                "kickoff_ts": rec.get("AD", "") or rec.get("ADE", ""),
                "round": rec.get("ER", ""),
                **header,
            }
    return None


def match_from_team_feed_pages(
    match_id: str,
    *,
    sport: int,
    country: int,
    team_key: str,
    max_pages: int = 40,
) -> Optional[Dict[str, str]]:
    """Как match_from_team_feed, но листает глубже (пр_ отдаёт по 20-30 матчей)."""
    return match_from_team_feed(
        match_id, sport=sport, country=country, team_key=team_key, max_pages=max_pages
    )


def match_from_tournament_feed(
    match_id: str,
    *,
    sport: int,
    country: int = DEFAULT_COUNTRY,
    tournament_key: str,
    season_id: str,
    max_pages: int = 40,
) -> Optional[Dict[str, str]]:
    """Найти матч в tr_-фиде турнира/сезона."""
    if not tournament_key or not season_id:
        return None
    country = country or DEFAULT_COUNTRY
    header: Dict[str, str] = {}
    for page in range(max_pages):
        url = feed_url(
            f"tr_{sport}_{country}_{tournament_key}_{season_id}_{page}_1_ru-kz_1"
        )
        try:
            text = fetch_feed(url, retries=2, timeout=40)
        except Exception:  # noqa: BLE001
            return None
        if not text or len(text) < 100:
            return None
        head = league_header(text)
        if head and not header:
            header = head
        for rec in _records(text):
            if rec.get("AA") != match_id:
                continue
            return {
                "match_id": match_id,
                "home_id": rec.get("PX", ""),
                "away_id": rec.get("PY", ""),
                "home_name": rec.get("AE", ""),
                "away_name": rec.get("AF", ""),
                "kickoff_ts": rec.get("AD", "") or rec.get("ADE", ""),
                "round": rec.get("ER", ""),
                **header,
            }
    return None


def resolve_match_ids_from_feed(
    match_id: str,
    *,
    sport: int = 1,
    country: Optional[int] = None,
    team_key: str = "",
    tournament_key: str = "",
    season_id: str = "",
) -> Dict[str, str]:
    """Собрать идентификаторы матча из фидов (без HTML).

    Порядок: pr_ по известному team_key → tr_ по турниру/сезону.
    Возвращает dict с ключами home_id/away_id/tournament_key/country_id/league_link
    и пустыми строками для того, что не нашлось.
    """
    country_id = country or DEFAULT_COUNTRY
    attempts: List[Dict[str, str]] = []

    # Если ключа команды нет — берём любой из h2h-фида и ищем матч в pr_.
    key = team_key or bootstrap_team_key(match_id, sport=sport)

    if key:
        found = match_from_team_feed(
            match_id, sport=sport, country=country_id, team_key=key
        )
        if found:
            attempts.append(found)

    if tournament_key and season_id:
        found = match_from_tournament_feed(
            match_id,
            sport=sport,
            country=country_id,
            tournament_key=tournament_key,
            season_id=season_id,
        )
        if found:
            attempts.append(found)

    for found in attempts:
        if found.get("home_id") and found.get("away_id"):
            return {
                "home_id": found["home_id"],
                "away_id": found["away_id"],
                "tournament_key": found.get("ZEE", "") or tournament_key,
                "country_id": found.get("ZB", "") or str(country_id),
                "league_link": found.get("ZL", ""),
                "home_name": found.get("home_name", ""),
                "away_name": found.get("away_name", ""),
                "source": "feed",
            }

    return {}


def teams_from_h2h_feed(match_id: str, *, sport: int = 1) -> Tuple[str, str, str, str]:
    """Ключи команд из df_hh-фида (когда HTML-страница недоступна).

    df_hh содержит секции «Последние игры: <команда>» (KB), а в каждой игре —
    ключи участников UQ/UO и имена KJ/KK (у соперника имя с «*»).
    Возвращает (home_key, away_key, home_name, away_name) для запрошенного матча;
    пустые строки, если блок не найден.
    """
    url = feed_url(f"df_hh_{sport}_{match_id}")
    try:
        text = fetch_feed(url, retries=2, timeout=30)
    except Exception:  # noqa: BLE001
        return "", "", "", ""
    section_team = ""
    for rec in _records(text):
        if rec.get("KB"):
            section_team = rec["KB"].split(":", 1)[-1].strip()
            continue
        if rec.get("KP") != match_id and rec.get("AA") != match_id:
            continue
        uq = rec.get("UQ", "")
        uo = rec.get("UO", "")
        kj = rec.get("KJ", "")
        kk = rec.get("KK", "")
        if not uq or not uo:
            continue
        # KJ — хозяин, KK — гость; у гостя в истории имя со звёздочкой.
        home_name = kj.lstrip("*").strip()
        away_name = kk.lstrip("*").strip()
        if section_team and home_name and section_team != home_name:
            return uo, uq, away_name, home_name
        return uq, uo, home_name, away_name
    return "", "", "", ""


def bootstrap_team_key(match_id: str, *, sport: int = 1) -> str:
    """Любой ключ команды этого матча — чтобы найти его в pr_-фиде."""
    home_key, away_key, _, _ = teams_from_h2h_feed(match_id, sport=sport)
    return home_key or away_key


def match_start_ts(match_id: str, *, sport: int = 1) -> int:
    """Kickoff timestamp матча из dc_-фида (поле DC), 0 если не нашлось.

    DC — время начала, DD/DK — время обновления. Нужен, когда расчёт не дал
    start_ts: без него дата матча в matches пустая.
    """
    url = feed_url(f"dc_{sport}_{match_id}")
    try:
        text = fetch_feed(url, retries=1, timeout=20)
    except Exception:  # noqa: BLE001
        return 0
    for rec in _records(text):
        for key in ("DC", "AD", "ADE"):
            value = rec.get(key)
            if not value:
                continue
            try:
                ts = int(float(str(value).strip()))
            except (TypeError, ValueError):
                continue
            if ts > 0:
                return ts
    return 0
