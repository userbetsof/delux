"""Загрузка данных для анализа матча (порт VBA getGame / getTable)."""

from __future__ import annotations

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


def fetch_match_page_html(match_id: str) -> str:
    from flashscore_feed import API_HEADERS

    last_err: Optional[BaseException] = None
    url = f"https://{MATCH_PAGE_HOST}/match/{match_id}/"
    try:
        req = __import__("urllib.request").request.Request(
            url, headers={**dict(API_HEADERS), "Referer": f"https://{MATCH_PAGE_HOST}/"}
        )
        with __import__("urllib.request").request.urlopen(req, timeout=12) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        last_err = exc
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


def fetch_match_page_ids(match_id: str) -> Tuple[str, str, str, str]:
    html = fetch_match_page_html(match_id)

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

    return home_id, away_id, stage, tournament


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

        item = HistoryMatch(
            tour_name=data.get("KF", ""),
            date=date_str,
            home_name=data.get("KJ", "").replace("*", ""),
            away_name=data.get("KK", "").replace("*", ""),
            home_ht=int(float(data.get("KU", "0") or 0)),
            away_ht=int(float(data.get("KT", "0") or 0)),
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

        # Футбол/хоккей: AT/AU полный счёт, BC/BD — 2-й тайм/период.
        # Бейсбол: AG/AH — финальный счёт, если AT/AU пусты.
        home_first = int(float(data.get("AT") or data.get("AG") or 0))
        away_first = int(float(data.get("AU") or data.get("AH") or 0))
        home_second = int(float(data.get("BC") or 0))
        away_second = int(float(data.get("BD") or 0))
        home_ht = home_first - home_second
        away_ht = away_first - away_second

        px = data.get("PX", "")
        py = data.get("PY", "")
        pid = (px if participant_field == "PX" else py) or px or py
        venue = "Дома" if (pid and pid == team_participant_id) else "Гости"

        item = HistoryMatch(
            tour_name=tour_name,
            date=date_str,
            home_name=home_name,
            away_name=away_name,
            home_ht=home_ht,
            away_ht=away_ht,
            home_st=home_second,
            away_st=away_second,
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
) -> Tuple[List[HistoryMatch], List[HistoryMatch], List[HistoryMatch]]:
    url = (
        f"https://{settings.sourcer}x/feed/pr_{settings.sport}_"
        f"{country_id}_{participant_id}_0_0{settings.suffix}"
    )
    return _parse_team_feed(url, settings, participant_id, "PX", exclude_match_id, before_dt)


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
    return _parse_team_feed(url, settings, participant_id, "PY", exclude_match_id, before_dt)


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


def fetch_table(settings: MatchSettings, match_id: str, table_name: str) -> List[TableRow]:
    rows = _fetch_table_once(settings, match_id, table_name)

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
    detected = detect_sport_from_match_page(match.match_id)
    if detected and detected != settings.sport:
        settings.sport = detected

    match.country_id = _normalize_flashscore_id(match.country_id)

    if not _participant_ids_look_valid(match):
        try:
            home_id, away_id, stage_id, tour_id = fetch_match_page_ids(match.match_id)
            match.home_participant_id = home_id
            match.away_participant_id = away_id
            match.tournament_stage_id = stage_id
            match.tournament_id = tour_id
        except Exception as exc:
            print(f"[!] match page ids unavailable ({exc})")

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
            # На всякий случай перечитаем участников со страницы
            if not _participant_ids_look_valid(match) or not home_all:
                try:
                    home_id, away_id, stage_id, tour_id = fetch_match_page_ids(match.match_id)
                    if home_id:
                        match.home_participant_id = home_id
                    if away_id:
                        match.away_participant_id = away_id
                    if stage_id:
                        match.tournament_stage_id = stage_id
                    if tour_id:
                        match.tournament_id = tour_id
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

    for name in TABLE_TYPES:
        setattr(payload, name, fetch_table(settings, match.match_id, name))

    return payload
