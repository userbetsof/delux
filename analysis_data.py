"""Загрузка данных для анализа матча (порт VBA getGame / getTable)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from flashscore_feed import (
    FLASHSCORE_HOST,
    FLASHSCORE_SOURCER,
    clean_team_name,
    fetch_feed,
    iter_feed_rows,
    map_source,
    parse_fields,
)

MATCH_PAGE_HOST = FLASHSCORE_HOST
PARTICIPANT_RE = re.compile(r'"id":"(\w{8})"')
TOURNAMENT_STAGE_RE = re.compile(r'"tournamentStage":"(\w{8})"')
TOURNAMENT_RE = re.compile(r'"tournament":"(\w{8})"')
TOURNAMENT_TEMPLATE_RE = re.compile(r'"tournamentTemplateId":"(\w{8})"')
SPORT_FROM_PAGE = (
    (re.compile(r"/baseball/", re.I), 6),
    (re.compile(r"/basketball/", re.I), 3),
    (re.compile(r"/hockey/", re.I), 4),
    (re.compile(r"/(?:football|soccer)/", re.I), 1),
)

TABLE_TYPES = {
    "table_overall": (1, "0"),
    "table_home": (2, "0"),
    "table_away": (3, "0"),
    "form_overall": (5, "0"),
    "form_home": (8, "0"),
    "form_away": (9, "0"),
}


@dataclass
class MatchSettings:
    sport: int = 1
    source: int = 2
    timezone: int = -7
    time_offset: int = 10
    sourcer: str = FLASHSCORE_SOURCER
    suffix: str = "_ru_1_"


@dataclass
class MatchInfo:
    match_id: str
    league: str = ""
    date: str = ""
    home: str = ""
    away: str = ""
    country_id: str = ""
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    home_participant_id: str = ""
    away_participant_id: str = ""
    tournament_stage_id: str = ""
    tournament_id: str = ""
    tournament_template_id: str = ""
    start_ts: Optional[int] = None
    status: Optional[int] = None  # 0 не начался / 1 live / 2 HT / 3 завершён


@dataclass
class HistoryMatch:
    tour_name: str
    date: str
    home_name: str
    away_name: str
    home_ht: int
    away_ht: int
    home_st: int
    away_st: int
    venue: str = ""


@dataclass
class TableRow:
    rank: str = ""
    team: str = ""
    played: str = ""
    wins: str = ""
    draws: str = ""
    losses: str = ""
    scored: str = ""
    conceded: str = ""
    points: str = ""


@dataclass
class AnalysisPayload:
    match: MatchInfo
    settings: MatchSettings
    h2h: List[HistoryMatch] = field(default_factory=list)
    h2h_home: List[HistoryMatch] = field(default_factory=list)
    home_all: List[HistoryMatch] = field(default_factory=list)
    home_home: List[HistoryMatch] = field(default_factory=list)
    home_away: List[HistoryMatch] = field(default_factory=list)
    away_all: List[HistoryMatch] = field(default_factory=list)
    away_home: List[HistoryMatch] = field(default_factory=list)
    away_away: List[HistoryMatch] = field(default_factory=list)
    table_overall: List[TableRow] = field(default_factory=list)
    table_home: List[TableRow] = field(default_factory=list)
    table_away: List[TableRow] = field(default_factory=list)
    form_overall: List[TableRow] = field(default_factory=list)
    form_home: List[TableRow] = field(default_factory=list)
    form_away: List[TableRow] = field(default_factory=list)


def build_settings(
    sport: int = 1,
    source: int = 2,
    tz_base: int = 16,
    dayzone_base: int = 8,
    time_offset: int = 10,
) -> MatchSettings:
    sourcer, suffix = map_source(source)
    timezone = int(tz_base) - (13 + int(time_offset))
    return MatchSettings(
        sport=int(sport),
        source=int(source),
        timezone=timezone,
        time_offset=int(time_offset),
        sourcer=sourcer,
        suffix=suffix,
    )


def _parse_match_datetime(date_str: str) -> Optional[datetime]:
    from date_utils import parse_match_datetime

    return parse_match_datetime(date_str)


def _ts_to_date(ts_value: str, timezone: int, time_offset: int = 0) -> str:
    from date_utils import format_ts_match_date

    return format_ts_match_date(ts_value, timezone, time_offset)


def fetch_match_page_html(match_id: str, *, retries: int = 2, timeout: int = 12) -> str:
    """HTML страницы матча. Один повтор: сайт часто рвёт TLS с первой попытки."""
    import time as _time
    import urllib.request

    from flashscore_feed import API_HEADERS

    last_err: Optional[BaseException] = None
    url = f"https://{MATCH_PAGE_HOST}/match/{match_id}/"
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(
                url, headers={**dict(API_HEADERS), "Referer": f"https://{MATCH_PAGE_HOST}/"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt + 1 < retries:
                _time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"fetch_match_page_html failed for {match_id}: {last_err}") from last_err


def detect_sport_from_html(html: str) -> Optional[int]:
    # Ищем URL текущего матча: /sport/team-home-team-away/?mid=XXX
    # sidebar содержит ссылки на все виды спорта, поэтому нельзя искать по всему HTML
    # Паттерн: /{sport}/.../?mid={match_id} (кавычки в HTML обрезают URL)
    pattern = re.compile(
        r"/(football|soccer|baseball|basketball|hockey)/[^\"'\s]*\?mid=", re.I
    )
    match = pattern.search(html)
    if match:
        sport_name = match.group(1).lower()
        return {"football": 1, "soccer": 1, "baseball": 6, "basketball": 3, "hockey": 4}.get(sport_name)
    return None


def detect_sport_from_match_page(match_id: str) -> Optional[int]:
    try:
        return detect_sport_from_html(fetch_match_page_html(match_id))
    except Exception:
        return None


def fetch_match_page_ids(
    match_id: str,
    *,
    sport: int = 1,
    country: Optional[int] = None,
    team_key: str = "",
    tournament_key: str = "",
    season_id: str = "",
) -> Tuple[str, str, str, str, str]:
    """Идентификаторы матча: HTML-страница, при недоступности — фиды.

    У части провайдеров страница /match/{id}/ блокируется (TLS-хендшейк), а
    машинные фиды *.flashscore.ninja доступны. Фиды дают participant id (PX/PY)
    и tournament key (ZEE), но не stage/seasonId — эти поля остаются пустыми,
    и season_id резолвится отдельно через tr_/df_ фиды.
    """
    try:
        html = fetch_match_page_html(match_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] страница матча недоступна ({exc}) — читаю фиды")
        return fetch_match_ids_from_feeds(
            match_id,
            sport=sport,
            country=country,
            team_key=team_key,
            tournament_key=tournament_key,
            season_id=season_id,
        )

    # На страницах бейсбола (и иногда других) первым идёт id самого матча —
    # его нельзя брать как participantEncodedId, иначе pr_* пустой и ДомаДома пустая.
    ids: List[str] = []
    seen: set[str] = set()
    for pid in PARTICIPANT_RE.findall(html):
        if not pid or pid == match_id or pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)
    home_id = ids[0] if len(ids) > 0 else ""
    away_id = ids[1] if len(ids) > 1 else ""

    stage = ""
    m = TOURNAMENT_STAGE_RE.search(html)
    if m:
        stage = m.group(1)

    tournament = ""
    m = TOURNAMENT_RE.search(html)
    if m:
        tournament = m.group(1)

    template = ""
    m = TOURNAMENT_TEMPLATE_RE.search(html)
    if m:
        template = m.group(1)

    return home_id, away_id, stage, tournament, template


def fetch_match_ids_from_feeds(
    match_id: str,
    *,
    sport: int = 1,
    country: Optional[int] = None,
    team_key: str = "",
    tournament_key: str = "",
    season_id: str = "",
) -> Tuple[str, str, str, str, str]:
    """(home_id, away_id, stage, tournament, template) из фидов вместо HTML."""
    try:
        from feed_ids import resolve_match_ids_from_feed
    except Exception:  # noqa: BLE001
        return "", "", "", "", ""

    data = resolve_match_ids_from_feed(
        match_id,
        sport=sport,
        country=country,
        team_key=team_key,
        tournament_key=tournament_key,
        season_id=season_id,
    )
    if not data:
        return "", "", "", "", ""
    return (
        data.get("home_id", ""),
        data.get("away_id", ""),
        "",  # stage в фидах отсутствует
        "",  # tournament (стадия) — тоже
        data.get("tournament_key", ""),
    )


def _apply_feed_ids(match: "MatchInfo", *, sport: int) -> None:
    """Дополнить матч тем, что дают фиды: participant id, country, ключ турнира."""
    try:
        from feed_ids import resolve_match_ids_from_feed
    except Exception:  # noqa: BLE001
        return

    country = int(match.country_id) if (match.country_id or "").isdigit() else None
    data = resolve_match_ids_from_feed(
        match.match_id,
        sport=sport,
        country=country,
        team_key=match.home_participant_id or match.away_participant_id,
        tournament_key=match.tournament_template_id,
    )
    if not data:
        return
    if data.get("home_id") and not match.home_participant_id:
        match.home_participant_id = data["home_id"]
    if data.get("away_id") and not match.away_participant_id:
        match.away_participant_id = data["away_id"]
    if data.get("country_id") and not match.country_id:
        match.country_id = _normalize_flashscore_id(data["country_id"])
    if data.get("tournament_key") and not match.tournament_template_id:
        match.tournament_template_id = data["tournament_key"]
    if not match.home and data.get("home_name"):
        match.home = data["home_name"]
    if not match.away and data.get("away_name"):
        match.away = data["away_name"]


def resolve_match_meta_from_feed(
    match_id: str,
    settings: MatchSettings,
    *,
    dayzone: int = 0,
) -> Tuple[str, str, str, str]:
    """Вернуть (country_id, league, home, away) из дневной ленты f_{sport}."""
    url = (
        f"https://{settings.sourcer}x/feed/f_{settings.sport}_"
        f"{dayzone}_{settings.timezone}{settings.suffix}"
    )
    try:
        text = fetch_feed(url)
    except Exception:
        return "", "", "", ""

    country = ""
    league = ""
    for name, _val, fields in iter_feed_rows(text):
        data = parse_fields(fields)
        if name == "ZA":
            country = data.get("ZB", country)
            league = (data.get("ZA", "") or league).replace(" - Плей-офф", "")
            continue
        if name == "AA" and data.get("AA") == match_id:
            return (
                country,
                league,
                clean_team_name(data.get("AE", "")),
                clean_team_name(data.get("AF", "")),
            )
    return "", "", "", ""


def fetch_h2h(
    match_id: str,
    settings: MatchSettings,
    home_team: str,
    away_team: str,
    before_dt: Optional[datetime],
) -> Tuple[List[HistoryMatch], List[HistoryMatch]]:
    url = f"https://{settings.sourcer}x/feed/df_hh_1_{match_id}"
    text = fetch_feed(url)

    rows: List[HistoryMatch] = []
    rows_home: List[HistoryMatch] = []
    in_section = False

    for chunk in text.split("~"):
        if f"KB{chr(247)}Очные встречи" in chunk or "KB÷Очные встречи" in chunk:
            in_section = True
            continue
        if in_section and (f"KA{chr(247)}" in chunk or "KA÷" in chunk):
            break
        if not in_section:
            continue

        data = parse_fields(chunk.split("¬"))
        if not data.get("KJ") or not data.get("KK"):
            continue

        date_str = _ts_to_date(data.get("KC", ""), settings.timezone, settings.time_offset)
        match_dt = _parse_match_datetime(date_str)
        if before_dt and match_dt and match_dt >= before_dt:
            continue

        # KL — полный счёт матча (формат "X:Y"), KU/KT — счёт первого тайма/периода
        kl = data.get("KL", "")
        if kl and ":" in kl:
            parts = kl.split(":")
            home_ht = int(float(parts[0])) if len(parts) > 0 else 0
            away_ht = int(float(parts[1])) if len(parts) > 1 else 0
        else:
            home_ht = int(float(data.get("KU", "0") or 0))
            away_ht = int(float(data.get("KT", "0") or 0))
        item = HistoryMatch(
            tour_name=data.get("KF", ""),
            date=date_str,
            home_name=data.get("KJ", "").replace("*", ""),
            away_name=data.get("KK", "").replace("*", ""),
            home_ht=home_ht,
            away_ht=away_ht,
            home_st=0,
            away_st=0,
        )
        rows.append(item)
        if item.home_name == home_team:
            rows_home.append(item)

    rows.sort(key=lambda r: r.date, reverse=True)
    rows_home.sort(key=lambda r: r.date, reverse=True)
    return rows, rows_home


def _parse_team_feed(
    url: str,
    settings: MatchSettings,
    team_participant_id: str,
    participant_field: str,
    exclude_match_id: str,
    before_dt: Optional[datetime],
    *,
    is_away: bool = False,
) -> Tuple[List[HistoryMatch], List[HistoryMatch], List[HistoryMatch]]:
    text = fetch_feed(url)
    all_rows: List[HistoryMatch] = []
    home_rows: List[HistoryMatch] = []
    away_rows: List[HistoryMatch] = []

    tour_name = ""
    for fs_index_name, _val, fields in iter_feed_rows(text):
        data = parse_fields(fields)
        if fs_index_name == "ZA":
            tour_name = (data.get("ZA", "") or "").replace(" - Плей-офф", "")
            continue
        if fs_index_name != "AA":
            continue

        current_id = data.get("AA", "")
        if not current_id or current_id == exclude_match_id:
            continue

        date_str = _ts_to_date(data.get("AD", ""), settings.timezone)
        match_dt = _parse_match_datetime(date_str)
        if before_dt and match_dt and match_dt > before_dt:
            continue

        home_name = clean_team_name(data.get("AE", ""))
        away_name = clean_team_name(data.get("AF", ""))
        if not tour_name or not home_name:
            continue

        # pr_ feed (командная история):
        # AG/AH — финальный счёт (приоритет), AT/AU — первый тайм, BC/BD — 2-й тайм.
        ag = data.get("AG", "")
        ah = data.get("AH", "")
        if ag and ah:
            # AG/AH — финальный счёт
            home_ht = int(float(ag))
            away_ht = int(float(ah))
            home_st = 0
            away_st = 0
        else:
            home_first = int(float(data.get("AT") or 0))
            away_first = int(float(data.get("AU") or 0))
            home_second = int(float(data.get("BC") or 0))
            away_second = int(float(data.get("BD") or 0))
            home_ht = home_first - home_second
            away_ht = away_first - away_second
            home_st = home_second
            away_st = away_second

        px = data.get("PX", "")
        py = data.get("PY", "")
        pid = (px if participant_field == "PX" else py) or px or py
        # is_away=True: мы отслеживаем гостевую команду (PY).
        # Для гостевой команды: pid==away_id → "Гости", pid==home_id → "Дома".
        # is_away=False (по умолчанию): pid==home_id → "Дома", pid==away_id → "Гости".
        if pid and pid == team_participant_id:
            venue = "Гости" if is_away else "Дома"
        else:
            venue = "Дома" if is_away else "Гости"

        item = HistoryMatch(
            tour_name=tour_name,
            date=date_str,
            home_name=home_name,
            away_name=away_name,
            home_ht=home_ht,
            away_ht=away_ht,
            home_st=home_st,
            away_st=away_st,
            venue=venue,
        )
        all_rows.append(item)
        if venue == "Дома":
            home_rows.append(item)
        else:
            away_rows.append(item)

    for bucket in (all_rows, home_rows, away_rows):
        bucket.sort(key=lambda r: r.date, reverse=True)
    return all_rows, home_rows, away_rows


def fetch_team_history(
    settings: MatchSettings,
    country_id: str,
    participant_id: str,
    exclude_match_id: str,
    before_dt: Optional[datetime],
    *,
    max_pages: int = 24,
) -> Tuple[List[HistoryMatch], List[HistoryMatch], List[HistoryMatch]]:
    """История команды из pr_-фида.

    Для старых матчей первая страница содержит только свежие игры (2025-2026),
    и фильтр before_dt отбрасывает всё. Поэтому листаем, пока не наберём
    достаточно матчей ДО даты матча (или пока страницы не кончатся).
    """
    all_rows: List[HistoryMatch] = []
    home_rows: List[HistoryMatch] = []
    away_rows: List[HistoryMatch] = []
    seen: set[str] = set()

    for page in range(max_pages):
        url = (
            f"https://{settings.sourcer}x/feed/pr_{settings.sport}_"
            f"{country_id}_{participant_id}_{page}_0{settings.suffix}"
        )
        # Разбираем без фильтра: страницы идут от свежих к старым, и на первых
        # страницах матчей ДО нужной даты может не быть вовсе (матч 2015 года).
        a, h, w = _parse_team_feed(
            url, settings, participant_id, "PX", exclude_match_id, None, is_away=False
        )
        if not a and not h:
            break
        page_dates = []
        new = 0
        for bucket_src, bucket_dst in ((a, all_rows), (h, home_rows), (w, away_rows)):
            for row in bucket_src:
                key = f"{row.date}|{row.home_name}|{row.away_name}"
                if key in seen:
                    continue
                seen.add(key)
                bucket_dst.append(row)
                new += 1
                if row.date:
                    page_dates.append(row.date)
        if new == 0:
            break
        # Дошли до матчей раньше нужной даты — глубже только прошлое.
        if before_dt and page_dates:
            try:
                oldest = min(_parse_match_datetime(d) for d in page_dates)
                if oldest and oldest < before_dt:
                    break
            except (TypeError, ValueError):
                pass

    # Фильтр «только до матча» применяем после сбора.
    if before_dt:
        def _keep(rows: List[HistoryMatch]) -> List[HistoryMatch]:
            out = []
            for row in rows:
                try:
                    dt = _parse_match_datetime(row.date)
                except (TypeError, ValueError):
                    out.append(row)
                    continue
                if dt is None or dt < before_dt:
                    out.append(row)
            return out

        all_rows = _keep(all_rows)
        home_rows = _keep(home_rows)
        away_rows = _keep(away_rows)

    for bucket in (all_rows, home_rows, away_rows):
        bucket.sort(key=lambda r: r.date, reverse=True)
    return all_rows, home_rows, away_rows


def fetch_away_team_history(
    settings: MatchSettings,
    country_id: str,
    participant_id: str,
    exclude_match_id: str,
    before_dt: Optional[datetime],
) -> Tuple[List[HistoryMatch], List[HistoryMatch], List[HistoryMatch]]:
    url = (
        f"https://{settings.sourcer}x/feed/pr_{settings.sport}_"
        f"{country_id}_{participant_id}_0_0{settings.suffix}"
    )
    return _parse_team_feed(url, settings, participant_id, "PY", exclude_match_id, before_dt, is_away=True)


def _parse_table_feed(text: str, table_index: int, temper_value: str) -> List[TableRow]:
    rows: List[TableRow] = []
    temper = False

    for block in text.split("¬~"):
        parts = block.split("¬")
        if not parts:
            continue
        head = parts[0].split("÷")
        if len(head) < 2:
            continue
        index_name, index_value = head[0], head[1]

        if index_name == "ETI":
            temper = index_value == temper_value
            continue

        if index_name != "TR" or not temper:
            continue

        game: Dict[str, str] = {}
        for part in parts:
            p = part.split("÷")
            if len(p) < 2:
                continue
            key, val = p[0], p[1]
            if key == "TR":
                game["rank"] = val
            elif key == "TN":
                game["team"] = val
            elif key == "TM":
                game["played"] = val
            elif key in ("TWR", "OUO"):
                game["wins"] = val
            elif key in ("TDR", "OUU"):
                game["draws"] = val
            elif key == "TLR" and "losses" not in game:
                game["losses"] = val
            elif key == "TG":
                scored, conceded = (val.split(":") + ["0", "0"])[:2]
                if "scored" not in game:
                    game["scored"] = scored
                game["conceded"] = conceded
            elif key == "TP":
                game["points"] = val

        # Как в VBA getTable: form_overall (index 5) — только команды с ≥5 играми формы.
        if table_index == 5:
            try:
                played_n = int(float(game.get("played") or 0))
            except (TypeError, ValueError):
                played_n = 0
            if played_n < 5:
                continue

        if game.get("team"):
            rows.append(
                TableRow(
                    rank=game.get("rank", ""),
                    team=game.get("team", ""),
                    played=game.get("played", ""),
                    wins=game.get("wins", ""),
                    draws=game.get("draws", ""),
                    losses=game.get("losses", ""),
                    scored=game.get("scored", ""),
                    conceded=game.get("conceded", ""),
                    points=game.get("points", ""),
                )
            )
        if len(rows) >= 200:
            break

    return rows


def _fetch_table_once(settings: MatchSettings, match_id: str, table_name: str) -> List[TableRow]:
    table_index, temper_value = TABLE_TYPES[table_name]
    url = f"https://{settings.sourcer}x/feed/df_to_{settings.sport}_{match_id}_{table_index}"
    return _parse_table_feed(fetch_feed(url), table_index, temper_value)


_AL_MARKERS = (
    "Янкиз",
    "Ред Сокс",
    "Рэйс",
    "Ориолс",
    "Блю Джейс",
    "Уайт Сокс",
    "Гардианс",
    "Тайгерс",
    "Роялс",
    "Твинс",
    "Астрос",
    "Маринерс",
    "Рейнджерс",
    "Энджелс",
    "Athletics",
)


def _table_looks_al(rows: List[TableRow]) -> bool:
    for row in rows:
        name = row.team or ""
        if any(marker in name for marker in _AL_MARKERS):
            return True
    return False


def _list_mlb_match_ids(settings: MatchSettings, exclude_id: str) -> List[str]:
    """Другие матчи США: МЛБ из дневной ленты (для склейки AL+NL home/away)."""
    found: List[str] = []
    for dayzone in (0, 1, 2):
        url = (
            f"https://{settings.sourcer}x/feed/f_{settings.sport}_"
            f"{dayzone}_{settings.timezone}{settings.suffix}"
        )
        try:
            text = fetch_feed(url)
        except Exception:
            continue
        league = ""
        for name, _val, fields in iter_feed_rows(text):
            data = parse_fields(fields)
            if name == "ZA":
                league = data.get("ZA", "") or ""
                continue
            if name != "AA":
                continue
            mid = data.get("AA", "")
            if not mid or mid == exclude_id:
                continue
            if "МЛБ" not in league and "MLB" not in league.upper():
                continue
            if mid not in found:
                found.append(mid)
        if found:
            break
    return found


def _merge_baseball_conference_tables(
    primary: List[TableRow], secondary: List[TableRow]
) -> List[TableRow]:
    """Склеить AL+NL блоки. Порядок как в overall: сначала AL, потом NL."""
    primary_teams = {r.team for r in primary}
    secondary_teams = {r.team for r in secondary}
    new_teams = secondary_teams - primary_teams
    if len(new_teams) < 5:
        return primary

    primary_is_al = _table_looks_al(primary)
    secondary_is_al = _table_looks_al(secondary)
    if primary_is_al and not secondary_is_al:
        return primary + secondary
    if secondary_is_al and not primary_is_al:
        return secondary + primary
    return primary + secondary


def _list_league_match_ids(
    settings: MatchSettings,
    exclude_id: str,
    *,
    league_markers: tuple[str, ...],
    sport: Optional[int] = None,
) -> List[str]:
    """Другие матчи той же лиги из дневной ленты (для склейки home/away блоков)."""
    feed_sport = settings.sport if sport is None else sport
    found: List[str] = []
    for dayzone in (0, 1, 2):
        url = (
            f"https://{settings.sourcer}x/feed/f_{feed_sport}_"
            f"{dayzone}_{settings.timezone}{settings.suffix}"
        )
        try:
            text = fetch_feed(url)
        except Exception:
            continue
        league = ""
        for name, _val, fields in iter_feed_rows(text):
            data = parse_fields(fields)
            if name == "ZA":
                league = data.get("ZA", "") or ""
                continue
            if name != "AA":
                continue
            mid = data.get("AA", "")
            if not mid or mid == exclude_id:
                continue
            upper = league.upper()
            if not any(m in league or m in upper for m in league_markers):
                continue
            if mid not in found:
                found.append(mid)
        if found:
            break
    return found


def _merge_split_tables(
    primary: List[TableRow],
    secondary: List[TableRow],
    *,
    min_new_teams: int = 5,
) -> List[TableRow]:
    """Склеить два частичных блока без дублей (порядок: primary, затем новые)."""
    primary_teams = {r.team for r in primary}
    secondary_teams = {r.team for r in secondary}
    if len(secondary_teams - primary_teams) < min_new_teams:
        return primary
    if len(primary_teams - secondary_teams) < min_new_teams:
        return secondary
    return primary + [r for r in secondary if r.team not in primary_teams]


def _snapshot_table_rows(match_id: str, table_name: str) -> List[TableRow]:
    """Таблица из сохранённого снимка match_snapshot (standings_json/form_json).

    Нужна, когда сеть недоступна (страница лиги заблокирована) — иначе
    повторный анализ остаётся без таблицы и прогноз не считается.
    Снимок хранит {"overall": [...], "home": [...], "away": [...]}.
    """
    field = "form_json" if table_name.startswith("form_") else "standings_json"
    side = table_name.split("_", 1)[1] if "_" in table_name else "overall"
    try:
        from db import get_db_connection

        with get_db_connection() as conn:
            row = conn.execute(
                f"SELECT {field} FROM match_snapshot WHERE match_id = ?",
                (match_id,),
            ).fetchone()
    except Exception:  # noqa: BLE001
        return []
    if not row or not row[0]:
        return []
    try:
        payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    out: List[TableRow] = []
    for item in payload.get(side) or []:
        if not isinstance(item, dict) or not item.get("team"):
            continue
        out.append(
            TableRow(
                rank=str(item.get("rank", "")),
                team=str(item.get("team", "")),
                played=str(item.get("played", "")),
                wins=str(item.get("wins", "")),
                draws=str(item.get("draws", "")),
                losses=str(item.get("losses", "")),
                scored=str(item.get("scored", "")),
                conceded=str(item.get("conceded", "")),
                points=str(item.get("points", "")),
            )
        )
    return out


def fetch_table(settings: MatchSettings, match_id: str, table_name: str) -> List[TableRow]:
    # Сначала сеть; при сбое или пустом ответе — сохранённый снимок,
    # чтобы повторный анализ не остался без таблицы.
    try:
        rows = _fetch_table_once(settings, match_id, table_name)
    except Exception:  # noqa: BLE001
        rows = []
    if not rows:
        rows = _snapshot_table_rows(match_id, table_name)
        if rows:
            print(f"    [snapshot] {table_name}: {len(rows)} строк (сеть недоступна)")

    # MLB: home/away от Flashscore — только одна конференция (~15 команд).
    # Подтягиваем вторую из другого матча МЛБ дня.
    if (
        settings.sport == 6
        and table_name in ("table_home", "table_away", "form_home", "form_away")
        and len({r.team for r in rows}) < 28
    ):
        for sibling_id in _list_mlb_match_ids(settings, match_id):
            extra = _fetch_table_once(settings, sibling_id, table_name)
            merged = _merge_baseball_conference_tables(rows, extra)
            if len({r.team for r in merged}) > len({r.team for r in rows}):
                rows = merged
            if len({r.team for r in rows}) >= 28:
                break

    # НХЛ (4) / баскетбол (3): feed-индекс 2 отдаёт только домашний блок
    # (одну конференцию), индекс 3 — только гостевой. Из-за этого гостевая
    # команда не находится в Таблица!V, Расчеты!AB102 → #N/A и NTB пустой.
    # Склеиваем оба блока.
    if settings.sport in (3, 4) and table_name in (
        "table_home",
        "table_away",
        "form_home",
        "form_away",
    ):
        overall = _fetch_table_once(settings, match_id, "table_overall")
        total_teams = len({r.team for r in overall})
        if total_teams and len({r.team for r in rows}) < total_teams * 0.9:
            counterpart = {
                "table_home": "table_away",
                "table_away": "table_home",
                "form_home": "form_away",
                "form_away": "form_home",
            }[table_name]
            extra = _fetch_table_once(settings, match_id, counterpart)
            merged = _merge_split_tables(rows, extra)
            if len({r.team for r in merged}) > len({r.team for r in rows}):
                rows = merged

    # Фолбэк: если блоков всё ещё мало, добираем из другого матча той же лиги.
    if settings.sport in (3, 4) and table_name in (
        "table_home",
        "table_away",
        "form_home",
        "form_away",
    ):
        overall = _fetch_table_once(settings, match_id, "table_overall")
        total_teams = len({r.team for r in overall})
        if total_teams and len({r.team for r in rows}) < total_teams * 0.75:
            markers = ("НХЛ", "NHL") if settings.sport == 4 else ("НБА", "NBA")
            for sibling_id in _list_league_match_ids(
                settings,
                match_id,
                league_markers=markers,
                sport=settings.sport,
            ):
                extra = _fetch_table_once(settings, sibling_id, table_name)
                merged = _merge_split_tables(rows, extra)
                if len({r.team for r in merged}) > len({r.team for r in rows}):
                    rows = merged
                if len({r.team for r in rows}) >= total_teams * 0.9:
                    break

    return rows


def _team_played_games(rows: List[TableRow], team_name: str) -> Optional[int]:
    needle = (team_name or "").strip().casefold()
    if not needle:
        return None
    for row in rows:
        team = (row.team or "").strip().casefold()
        if not team:
            continue
        if team == needle or needle in team or team in needle:
            try:
                return int(float(row.played or 0))
            except (TypeError, ValueError):
                return 0
    return None


def season_games_ready(
    settings: MatchSettings,
    match_id: str,
    home: str,
    away: str,
    *,
    min_games: int = 5,
    table_cache: Optional[Dict[str, List[TableRow]]] = None,
) -> Tuple[bool, str]:
    """False, если у команды в таблице сезона сыграно меньше min_games туров."""
    if min_games <= 0 or not match_id:
        return True, ""
    cache = table_cache if table_cache is not None else {}
    if match_id not in cache:
        try:
            cache[match_id] = fetch_table(settings, match_id, "table_overall")
        except Exception:
            cache[match_id] = []
    rows = cache.get(match_id) or []
    if not rows:
        return True, ""
    home_played = _team_played_games(rows, home)
    away_played = _team_played_games(rows, away)
    for label, team, played in (
        ("home", home, home_played),
        ("away", away, away_played),
    ):
        if played is not None and played < min_games:
            return False, f"{team or label}: тур={played} < {min_games}"
    return True, ""


def _normalize_flashscore_id(value: str) -> str:
    """Excel часто отдаёт country_id как 200.0 — в URL нужен 200."""
    s = (value or "").strip()
    if not s:
        return ""
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


def _participant_ids_look_valid(match: MatchInfo) -> bool:
    home = (match.home_participant_id or "").strip()
    away = (match.away_participant_id or "").strip()
    if not home or not away:
        return False
    # На бейсболе в Список!G иногда попадает сам match_id → pr_* пустой.
    if home == match.match_id or away == match.match_id:
        return False
    if home == away:
        return False
    return True


def load_analysis_data(match: MatchInfo, settings: MatchSettings) -> AnalysisPayload:
    before_dt = _parse_match_datetime(match.date)

    # Sport со страницы матча (иначе бейсбол с DELUX_SPORT=1 → пустой pr_* / ДомаДома).
    # Если страница недоступна — определение вида спорта молча пропускается,
    # остаётся settings.sport (из queued-матча).
    detected = detect_sport_from_match_page(match.match_id)
    if detected and detected != settings.sport:
        settings.sport = detected

    match.country_id = _normalize_flashscore_id(match.country_id)

    if not _participant_ids_look_valid(match) or not match.tournament_template_id:
        try:
            home_id, away_id, stage_id, tour_id, template_id = fetch_match_page_ids(
                match.match_id,
                sport=settings.sport,
                country=int(match.country_id) if match.country_id.isdigit() else None,
                team_key=match.home_participant_id or match.away_participant_id,
                tournament_key=match.tournament_template_id,
            )
            if home_id:
                match.home_participant_id = home_id
            if away_id:
                match.away_participant_id = away_id
            if stage_id and not match.tournament_stage_id:
                match.tournament_stage_id = stage_id
            if tour_id and not match.tournament_id:
                match.tournament_id = tour_id
            if template_id and not match.tournament_template_id:
                match.tournament_template_id = template_id
        except Exception as exc:
            print(f"[!] match page ids unavailable ({exc})")

    # Страница не дала полный набор (или заблокирована) — добираем из фидов.
    # Вызываем всегда: он заполняет только пустые поля (id, country, турнир, имена).
    _apply_feed_ids(match, sport=settings.sport)

    if not match.country_id or not match.home or not match.away:
        for dz in (0, 1, 2, 3):
            country, league, home, away = resolve_match_meta_from_feed(
                match.match_id, settings, dayzone=dz
            )
            if country or home:
                if country and not match.country_id:
                    match.country_id = _normalize_flashscore_id(country)
                if league and not match.league:
                    match.league = league
                if home and not match.home:
                    match.home = home
                if away and not match.away:
                    match.away = away
                break

    h2h, h2h_home = fetch_h2h(
        match.match_id, settings, match.home, match.away, before_dt
    )

    home_all, home_home, home_away = fetch_team_history(
        settings,
        match.country_id,
        match.home_participant_id,
        match.match_id,
        before_dt,
    )
    # Если country_id был неверный — pr_* пустой; переопределим из ленты и повторим.
    if not home_all and match.home_participant_id:
        for dz in (0, 1, 2, 3):
            country, league, home, away = resolve_match_meta_from_feed(
                match.match_id, settings, dayzone=dz
            )
            if not country:
                continue
            match.country_id = _normalize_flashscore_id(country)
            if league:
                match.league = league or match.league
            if home:
                match.home = home or match.home
            if away:
                match.away = away or match.away
            # На всякий случай перечитаем участников со страницы (или из фидов)
            if not _participant_ids_look_valid(match) or not home_all:
                try:
                    home_id, away_id, stage_id, tour_id, template_id = fetch_match_page_ids(
                        match.match_id,
                        sport=settings.sport,
                        country=int(match.country_id) if match.country_id.isdigit() else None,
                        team_key=match.home_participant_id or match.away_participant_id,
                        tournament_key=match.tournament_template_id,
                    )
                    if home_id:
                        match.home_participant_id = home_id
                    if away_id:
                        match.away_participant_id = away_id
                    if stage_id:
                        match.tournament_stage_id = stage_id
                    if tour_id:
                        match.tournament_id = tour_id
                    if template_id:
                        match.tournament_template_id = template_id
                except Exception as exc:
                    print(f"[!] match page ids retry skipped ({exc})")
            home_all, home_home, home_away = fetch_team_history(
                settings,
                match.country_id,
                match.home_participant_id,
                match.match_id,
                before_dt,
            )
            if home_all:
                break

    away_all, away_home, away_away = fetch_away_team_history(
        settings,
        match.country_id,
        match.away_participant_id,
        match.match_id,
        before_dt,
    )

    payload = AnalysisPayload(
        match=match,
        settings=settings,
        h2h=h2h,
        h2h_home=h2h_home,
        home_all=home_all,
        home_home=home_home,
        home_away=home_away,
        away_all=away_all,
        away_home=away_home,
        away_away=away_away,
    )

    # Таблица берётся через текущий df_to_ API (как для предстоящих матчей).
    # Историческая реконструкция таблицы для завершённых матчей выполняется
    # отдельно в match_analysis.analyze_match (развилка по match_status == 3).
    for name in TABLE_TYPES:
        setattr(payload, name, fetch_table(settings, match.match_id, name))

    return payload
