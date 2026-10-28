"""Архивация исторических матчей из Flashscore.

Ограничения Flashscore API:
- f_* feed поддерживает только dayzone 0-3 (сегодня через ~2 дня назад)
- df_to_* (таблица/форма) возвращает ТЕКУЩИЕ данные, не исторические
- df_hh и pr_* можно фильтровать по before_dt (показывают матчи ДО целевой даты)

Решение: форма/таблица будут ТЕКУЩИЕ, но H2H и история команд — исторические.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from date_utils import normalize_match_date, parse_match_datetime
from flashscore_feed import FLASHSCORE_SOURCER, FIELD_SEP, ROW_SEP, fetch_feed


# ============================================================================
# КОНСТАНТЫ
# ============================================================================

SPORT_NAMES = {1: "Football", 3: "Basketball", 4: "Hockey", 6: "Baseball"}
DAYZONE_LIMIT = 3  # f_* feed поддерживает dayzone 0-3


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ FLASHSCORE
# ============================================================================

def fetch_feed_safe(url: str) -> str:
    """Безопасная загрузка фида с обработкой ошибок."""
    try:
        return fetch_feed(url)
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}")
        return ""


def parse_simple_feed(text: str) -> List[Dict[str, str]]:
    """Парсит простой feed Flashscore (строки через ROW_SEP, поля через FIELD_SEP)."""
    from flashscore_feed import FIELD_SEP, ROW_SEP

    if not text:
        return []

    pairs: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    for chunk in text.replace("~", ROW_SEP).split(ROW_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, sep, value = chunk.partition(FIELD_SEP)
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "MIT":
            if current:
                pairs.append(current)
            current = {}
        elif key == "MIV":
            current[value] = ""
        else:
            current[key] = value

    if current:
        pairs.append(current)

    return pairs


def extract_match_id_from_dc(dc_text: str) -> Optional[str]:
    """Извлекает match_id из dc_ фида."""
    from flashscore_feed import FIELD_SEP, ROW_SEP

    for chunk in (dc_text or "").replace("~", ROW_SEP).split(ROW_SEP):
        if f"MIT{FIELD_SEP}" in chunk or "MIT" in chunk:
            continue
        key, sep, value = chunk.partition(FIELD_SEP)
        if sep and key == "EID":
            return value.strip()
    return None


# ============================================================================
# ПОИСК MATCH_ID
# ============================================================================

def get_matches_for_date(date_str: str, sport: int = 1) -> List[Dict[str, Any]]:
    """
    Ищем match_id для конкретной даты.
    Для recent дат используем f_{sport}_{dayzone}.
    Для older дат — scrape через dc_ feed.
    """
    from date_utils import parse_date

    target_date = parse_date(date_str)
    dayzone = (datetime.now() - target_date).days

    if 0 <= dayzone <= DAYZONE_LIMIT:
        return _get_matches_from_feed(date_str, sport, dayzone)
    else:
        return _get_matches_from_scrape(date_str, sport)


def _get_matches_from_feed(date_str: str, sport: int, dayzone: int) -> List[Dict[str, Any]]:
    """Получаем матчи из f_{sport}_{dayzone}."""
    sourcer = FLASHSCORE_SOURCER
    url = f"https://{sourcer}x/feed/f_{int(sport)}_{dayzone}"
    text = fetch_feed_safe(url)

    if not text:
        return []

    matches = parse_simple_feed(text)
    result = []
    for m in matches:
        match_id = m.get("EID", "")
        if match_id:
            result.append({
                "match_id": match_id,
                "sport": sport,
                "date": date_str,
            })

    return result


def _get_matches_from_scrape(date_str: str, sport: int) -> List[Dict[str, Any]]:
    """
    Для старых дат — ищем матчи через scrape HTML.
    Используем dc_ feed для поиска match_id.
    """
    # Для более старых дат используем pr_ feed с before_dt
    from date_utils import format_date_flashscore

    before_dt = format_date_flashscore(date_str)
    matches = []

    # Пробуем через pr_ feed для каждой лиги
    # Это упрощённая версия — в реальности нужно перебирать лиги
    print(f"  [WARN] Scrape для даты {date_str} требует перебора лиг")
    print(f"  [WARN] Используйте --match-id для конкретных матчей")

    return matches


# ============================================================================
# АРХИВАЦИЯ ОДНОГО МАТЧА
# ============================================================================

def archive_match(match_id: str, sport: int, date_match: Optional[str] = None) -> Dict[str, Any]:
    """
    Загружаем все доступные фиды для матча и сохраняем в БД.
    """
    result = {
        "match_id": match_id,
        "sport": sport,
        "feeds_fetched": [],
        "feeds_success": [],
        "feeds_failed": [],
        "saved": False,
    }

    print(f"\n[ARCHIVE] Processing match {match_id} (sport={sport})")

    # 1. dc_{sport}_{match_id} — детали матча
    dc_text = fetch_feed_safe(f"https://{FLASHSCORE_SOURCER}x/feed/dc_{int(sport)}_{match_id}")
    result["feeds_fetched"].append("dc")
    if dc_text:
        result["feeds_success"].append("dc")
        # Извлекаем координаты, коэфф. и т.д.
        _save_dc_data(match_id, dc_text, result)
    else:
        result["feeds_failed"].append("dc")

    # 2. df_sui_{sport}_{match_id} — судья, стадион, зрители
    sui_text = fetch_feed_safe(f"https://{FLASHSCORE_SOURCER}x/feed/df_sui_{int(sport)}_{match_id}")
    result["feeds_fetched"].append("df_sui")
    if sui_text:
        result["feeds_success"].append("df_sui")
        _save_sui_data(match_id, sui_text, result)
    else:
        result["feeds_failed"].append("df_sui")

    # 3. df_hh_{sport}_{match_id} — H2H (фильтруется по дате на клиенте)
    hh_url = f"https://{FLASHSCORE_SOURCER}x/feed/df_hh_{int(sport)}_{match_id}"
    hh_text = fetch_feed_safe(hh_url)
    result["feeds_fetched"].append("df_hh")

    before_dt: Optional[datetime] = None
    if date_match:
        before_dt = parse_match_datetime(date_match)

    if hh_text:
        result["feeds_success"].append("df_hh")
        _save_h2h_data(match_id, hh_text, result, before_dt)
    else:
        result["feeds_failed"].append("df_hh")

    # 4. pr_{sport}_{country}_{participant} — история команд (фильтруется по дате)
    if date_match and before_dt:
        _save_team_history(match_id, sport, date_match, before_dt, result)
    else:
        result["feeds_failed"].append("pr (no before_dt)")

    # 5. df_st_{sport}_{match_id} — статистика матча
    st_text = fetch_feed_safe(f"https://{FLASHSCORE_SOURCER}x/feed/df_st_{int(sport)}_{match_id}")
    result["feeds_fetched"].append("df_st")
    if st_text:
        result["feeds_success"].append("df_st")
        _save_stats_data(match_id, st_text, result)
    else:
        result["feeds_failed"].append("df_st")

    # 6. df_to_{sport}_{match_id}_{idx} — текущая таблица/форма
    for idx in range(1, 4):
        to_text = fetch_feed_safe(f"https://{FLASHSCORE_SOURCER}x/feed/df_to_{int(sport)}_{match_id}_{idx}")
        if to_text:
            result["feeds_fetched"].append(f"df_to_{idx}")
            result["feeds_success"].append(f"df_to_{idx}")

    # 7. Сохраняем сырой JSON в match_snapshot
    _save_raw_json(match_id, result)

    # Помечаем как archived
    # _mark_as_archived(match_id)

    result["saved"] = True
    return result


def _to_flashscore_dt(date_str: str) -> str:
    """Конвертирует дату в формат Flashscore (YYYYMMDDHHmmss)."""
    try:
        dt = datetime.strptime(date_str, "%Y.%m.%d")
        return dt.strftime("%Y%m%d000000")
    except ValueError:
        return ""


def _filter_h2h_by_date(hh_text: str, before_dt: datetime) -> str:
    """Фильтрует H2H данные, оставляя только матчи ДО before_dt.
    
    Как в analysis_data.py: сравнивает parsed datetime каждого матча.
    """
    filtered_parts = []
    for chunk in hh_text.replace("~", ROW_SEP).split(ROW_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        
        data = {}
        parts = chunk.split(FIELD_SEP)
        if len(parts) >= 2:
            key, value = parts[0].strip(), parts[1].strip()
            data[key] = value
        
        # Ищем дату матча (поле KC — timestamp)
        date_ts = ""
        for part in chunk.split(ROW_SEP):
            parts = part.split(FIELD_SEP)
            if len(parts) >= 2 and parts[0].strip() == "KC":
                date_ts = parts[1].strip()
                break
        
        if not date_ts:
            # Нет даты — включаем
            filtered_parts.append(chunk)
            continue
        
        # Конвертируем timestamp в datetime
        try:
            ts = float(date_ts)
            match_dt = datetime.utcfromtimestamp(ts)
            if match_dt < before_dt:
                filtered_parts.append(chunk)
        except (ValueError, OverflowError, OSError):
            # Не удалось распарсить — включаем
            filtered_parts.append(chunk)
    
    return "~".join(filtered_parts)


def _filter_team_history_by_date(history_text: str, before_dt: datetime, exclude_match_id: str = "") -> str:
    """Фильтрует историю команд, оставляя только матчи ДО before_dt.
    
    Как в analysis_data.py: сравнивает parsed datetime каждого матча.
    """
    filtered_parts = []
    
    for chunk in history_text.replace("~", ROW_SEP).split(ROW_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        
        # Ищем ID матча (поле AA)
        match_id = ""
        date_ts = ""
        
        for part in chunk.split(ROW_SEP):
            parts = part.split(FIELD_SEP)
            if len(parts) >= 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key == "AA":
                    match_id = value
                elif key == "AD":
                    date_ts = value
        
        # Исключаем текущий матч
        if match_id == exclude_match_id:
            continue
        
        if not date_ts:
            # Нет даты — включаем
            filtered_parts.append(chunk)
            continue
        
        # Конвертируем timestamp в datetime
        try:
            ts = float(date_ts)
            match_dt = datetime.utcfromtimestamp(ts)
            if match_dt <= before_dt:
                filtered_parts.append(chunk)
        except (ValueError, OverflowError, OSError):
            # Не удалось распарсить — включаем
            filtered_parts.append(chunk)
    
    return "~".join(filtered_parts)


def _save_dc_data(match_id: str, dc_text: str, result: Dict[str, Any]) -> None:
    """Сохраняем данные из dc_ фида."""
    from db import get_db_connection

    pairs = parse_simple_feed(dc_text)
    data = {"EID": match_id}
    for p in pairs:
        data.update(p)

    # Извлекаем country_id (ZB) и participant IDs (PX, PY)
    for p in pairs:
        if p.get("ZB"):
            data["country_id"] = p["ZB"]
        if p.get("PX"):
            data["home_participant_id"] = p["PX"]
        if p.get("PY"):
            data["away_participant_id"] = p["PY"]

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO match_snapshot (match_id, raw_json, fetched_at) VALUES (?, ?, datetime('now'))",
            (match_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()


def _save_sui_data(match_id: str, sui_text: str, result: Dict[str, Any]) -> None:
    """Сохраняем данные из df_sui_ фида (судья, стадион, зрители)."""
    from db import upsert_match_snapshot
    from match_snapshot import parse_match_info

    data = parse_match_info(sui_text)
    if data:
        upsert_match_snapshot(match_id, data)


def _save_h2h_data(match_id: str, hh_text: str, result: Dict[str, Any],
                   before_dt: Optional[datetime] = None) -> None:
    """Сохраняем H2H данные. before_dt фильтруется на клиенте (как в analysis_data.py)."""
    from db import upsert_match_snapshot

    # Фильтруем H2H по дате на клиенте (Flashscore не поддерживает before_dt в URL)
    if hh_text and before_dt:
        hh_text = _filter_h2h_by_date(hh_text, before_dt)

    data = {"h2h_json": hh_text}
    upsert_match_snapshot(match_id, data)


def _save_team_history(match_id: str, sport: int, date_match: str, before_dt: datetime, result: Dict[str, Any]) -> None:
    """Сохраняем историю команд (pr_ feed). Фильтруется по дате на клиенте.
    
    pr_* feed НЕ поддерживает before_dt в URL — фильтруем как в analysis_data.py.
    URL формат: pr_{sport}_{country_id}_{participant_id}_0_0
    """
    from db import upsert_match_snapshot

    # Получаем country_id и participant_id из dc_ фида или match_snapshot
    from db import get_db_connection
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT home_team_id, away_team_id FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()

    if not row:
        result["feeds_failed"].append("pr (no match in DB)")
        return

    # Извлекаем participant_id из dc_ raw_json
    with get_db_connection() as conn:
        snap = conn.execute(
            "SELECT raw_json FROM match_snapshot WHERE match_id = ?",
            (match_id,),
        ).fetchone()

    home_pid = ""
    away_pid = ""
    country_id = ""

    if snap and snap.get("raw_json"):
        try:
            dc_data = json.loads(snap["raw_json"])
            # Ищем participant IDs в dc_ данных
            for key, val in dc_data.items():
                if key in ("PX", "PY"):
                    if key == "PX":
                        home_pid = str(val or "")
                    else:
                        away_pid = str(val or "")
                elif key == "ZB":
                    country_id = str(val or "")
        except (json.JSONDecodeError, TypeError):
            pass

    # Если не нашли — пробуем из HTML страницы матча
    if not home_pid or not away_pid:
        pids = _extract_participant_ids(match_id)
        home_pid = pids.get("home", home_pid)
        away_pid = pids.get("away", away_pid)

    if not country_id:
        result["feeds_failed"].append("pr (no country_id)")
        return

    # Загружаем историю обеих команд (без before_dt в URL)
    for team_idx, pid in [(1, home_pid), (2, away_pid)]:
        if not pid:
            result["feeds_failed"].append(f"pr_{team_idx} (no participant_id)")
            continue

        pr_url = f"https://{FLASHSCORE_SOURCER}x/feed/pr_{int(sport)}_{country_id}_{pid}_0_0"
        pr_text = fetch_feed_safe(pr_url)
        if pr_text:
            pr_text = _filter_team_history_by_date(pr_text, before_dt, match_id)
            result["feeds_success"].append(f"pr_{team_idx}")
        else:
            result["feeds_failed"].append(f"pr_{team_idx}")


def _extract_participant_ids(match_id: str) -> Dict[str, str]:
    # Извлекает participant_id из HTML страницы матча (как в analysis_data.py)
    import urllib.request
    from flashscore_feed import API_HEADERS

    result = {"home": "", "away": ""}
    try:
        url = f"https://{FLASHSCORE_SOURCER}x/match/{match_id}/"
        req = urllib.request.Request(
            url, headers={**dict(API_HEADERS), "Referer": f"https://{FLASHSCORE_SOURCER}x/"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        ids = []
        seen = set()
        for pid in re.findall(r'"id":"(\w{8})"', html):
            if not pid or pid == match_id or pid in seen:
                continue
            seen.add(pid)
            ids.append(pid)

        if len(ids) > 0:
            result["home"] = ids[0]
        if len(ids) > 1:
            result["away"] = ids[1]
    except Exception as e:
        print(f"  [WARN] Failed to extract participant IDs: {e}")

    return result


def _save_stats_data(match_id: str, st_text: str, result: Dict[str, Any]) -> None:
    """Сохраняем статистику матча."""
    from db import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO match_stats (match_id, stats_json, fetched_at) VALUES (?, ?, datetime('now'))",
            (match_id, st_text),
        )
        conn.commit()


def _save_raw_json(match_id: str, result: Dict[str, Any]) -> None:
    """Сохраняем полный JSON результата архивации."""
    from db import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO match_snapshot (match_id, raw_json, fetched_at) VALUES (?, ?, datetime('now'))",
            (match_id, json.dumps(result, ensure_ascii=False, default=str)),
        )
        conn.commit()


def _mark_as_archived(match_id: str) -> None:
    """Помечаем матч как archived."""
    from db import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE matches SET is_archived = 1 WHERE match_id = ?",
            (match_id,),
        )
        conn.commit()


# ============================================================================
# АРХИВАЦИЯ ДАТЫ / ПЕРИОДА
# ============================================================================

def archive_date(date_str: str, sport: int = 1) -> List[Dict[str, Any]]:
    """Архивация всех матчей за дату."""
    print(f"\n{'='*60}")
    print(f"[ARCHIVE] Date: {date_str}, Sport: {SPORT_NAMES.get(sport, sport)}")
    print(f"{'='*60}")

    matches = get_matches_for_date(date_str, sport)
    if not matches:
        print(f"  [WARN] No matches found for {date_str}")
        return []

    print(f"  Found {len(matches)} matches")

    results = []
    for i, match in enumerate(matches, 1):
        print(f"\n[{i}/{len(matches)}] {match['match_id']}")
        result = archive_match(
            match["match_id"],
            match["sport"],
            match["date"],
        )
        results.append(result)

        # Небольшая задержка между запросами
        time.sleep(0.5)

    success = sum(1 for r in results if r["saved"])
    print(f"\n[ARCHIVE] Completed: {success}/{len(results)} matches archived")

    return results


def archive_days(days: int, sport: int = 1) -> List[Dict[str, Any]]:
    """Архивация за последние N дней."""
    all_results = []
    today = datetime.now()

    for day_offset in range(min(days, DAYZONE_LIMIT), 0, -1):
        target_date = today - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y.%m.%d")

        print(f"\n{'#'*60}")
        print(f"[ARCHIVE] Processing: {date_str} (offset={day_offset} days)")
        print(f"{'#'*60}")

        results = archive_date(date_str, sport)
        all_results.extend(results)

        # Задержка между днями
        time.sleep(1)

    return all_results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Архивация исторических матчей из Flashscore",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --match-id
    p_match = sub.add_parser("match", help="Архивация одного матча")
    p_match.add_argument("--match-id", required=True, help="Flashscore match ID")
    p_match.add_argument("--sport", type=int, default=1, help="ID вида спорта (1=Football)")

    # --date
    p_date = sub.add_parser("date", help="Архивация всех матчей за дату")
    p_date.add_argument("--date", required=True, help="Дата в формате YYYY.MM.DD")
    p_date.add_argument("--sport", type=int, default=1, help="ID вида спорта")

    # --days
    p_days = sub.add_parser("days", help="Архивация за последние N дней")
    p_days.add_argument("--days", type=int, default=7, help="Количество дней")
    p_days.add_argument("--sport", type=int, default=1, help="ID вида спорта")

    args = parser.parse_args()

    if args.command == "match":
        result = archive_match(args.match_id, args.sport)
        print(f"\n[RESULT] Match {args.match_id}: saved={result['saved']}")
        print(f"  Success: {result['feeds_success']}")
        print(f"  Failed: {result['feeds_failed']}")

    elif args.command == "date":
        results = archive_date(args.date, args.sport)
        print(f"\n[SUMMARY] Archived {len(results)} matches for {args.date}")

    elif args.command == "days":
        results = archive_days(args.days, args.sport)
        print(f"\n[SUMMARY] Archived {len(results)} matches for last {args.days} days")


if __name__ == "__main__":
    main()
