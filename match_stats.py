"""Сбор и парсинг статистики по последним 10 матчам команд из Flashscore."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from flashscore_feed import (
    API_HEADERS,
    FLASHSCORE_HOST,
    fetch_feed,
    iter_feed_rows,
    parse_fields,
)

# Регулярка для извлечения числа из значений типа "70 (188/269)"
NUMBER_WITH_EXTRA = re.compile(r'^([\d.]+)')

# Коды статистики (ID -> название)
STAT_CODES = {
    "12": "Владение мячом",
    "13": "Удары в створ",
    "14": "Удары мимо",
    "15": "Штрафные",
    "16": "Угловые",
    "17": "Офсайды",
    "18": "Вбрасывания",
    "23": "Желтые карточки",
    "34": "Всего ударов",
    "43": "Опасные атаки",
    "44": "Атаки",
}

STAT_PATTERN = re.compile(r"^(1[0-9]|2[0-3]|3[0-4]|4[0-4])$")


def _extract_number(value: str) -> float:
    """Извлечение числа из строки: '70', '70%', '70 (188/269)' -> 70.0"""
    if not value:
        return 0.0
    value = value.strip().replace("%", "")
    if value == "-":
        return 0.0
    match = NUMBER_WITH_EXTRA.match(value)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def match_stats_feed_url(
    match_id: str,
    *,
    sport: int = 1,
    sourcer: str = FLASHSCORE_HOST,
) -> str:
    """URL фида статистики матча."""
    # sourcer может прийти как "www.flashscorekz.com/" (FLASHSCORE_SOURCER) —
    # убираем хвостовой слэш, иначе получается "//x/feed/" и 404.
    host = (sourcer or "").rstrip("/")
    return f"https://{host}/x/feed/df_st_{int(sport)}_{match_id}"


def parse_match_stats(text: str) -> Dict[str, Any]:
    """Парсинг статистики из фида df_st."""
    result: Dict[str, Any] = {
        "periods": [],
        "match": {},
    }
    
    current_period = None
    current_category = None
    
    for row_type, row_id, fields in iter_feed_rows(text):
        parsed = parse_fields(fields)
        
        if row_type == "SE":
            # Секция (период): SE÷Match¬SG÷Match
            current_period = parsed.get("SG", row_id)
            if current_period not in result["periods"]:
                result["periods"].append(current_period)
            result.setdefault(current_period, {})
            
        elif row_type == "SF":
            # Категория: SF÷Shots¬SG÷Удары
            current_category = parsed.get("SG", row_id)
            if current_category and current_period:
                result.setdefault(current_period, {}).setdefault("categories", {})[current_category] = []
                
        elif row_type == "SD":
            # Статистика: SD÷13¬SG÷Удары в створ¬SH÷5¬SI÷3
            stat_id = row_id
            stat_name = parsed.get("SG", STAT_CODES.get(stat_id, stat_id))
            home_value = parsed.get("SH", "0")
            away_value = parsed.get("SI", "0")
            
            # Извлечение чисел (обрабатываем '70 (188/269)', '70%', '70', '-')
            home_num = _extract_number(home_value)
            away_num = _extract_number(away_value)
            
            stat_data = {
                "id": stat_id,
                "name": stat_name,
                "home": home_num,
                "away": away_num,
            }
            
            if current_period and current_category:
                result.setdefault(current_period, {}).setdefault("categories", {}).setdefault(
                    current_category, []
                ).append(stat_data)
            elif current_period:
                result[current_period][stat_name] = stat_data
    
    # Собираем общую статистику матча (период "Match" или "Матч")
    match_period = result.get("Match") or result.get("Матч", {})
    if match_period and isinstance(match_period, dict):
        categories = match_period.get("categories", {})
        if categories:
            for cat_name, cat_stats in categories.items():
                for stat in cat_stats:
                    key = f"{cat_name}_{stat['name']}"
                    result["match"][key] = {
                        "home": stat["home"],
                        "away": stat["away"],
                    }
    
    return result


def fetch_match_stats(
    match_id: str,
    *,
    sport: int = 1,
    sourcer: str = FLASHSCORE_HOST,
) -> Optional[Dict[str, Any]]:
    """Загрузка и парсинг статистики матча."""
    url = match_stats_feed_url(match_id, sport=sport, sourcer=sourcer)
    try:
        text = fetch_feed(url)
        return parse_match_stats(text)
    except Exception as exc:
        print(f"    [!] статистика {match_id}: {exc}")
        return None


def save_match_stats(
    match_id: str,
    stats: Dict[str, Any],
) -> None:
    """Сохранение статистики матча в БД."""
    import json
    
    from db import get_db_connection
    
    # Преобразуем в плоский формат для хранения
    flat_stats: Dict[str, Any] = {}
    
    for period_name, period_data in stats.items():
        if period_name == "match":
            continue
        if isinstance(period_data, dict):
            for cat_name, cat_stats in period_data.get("categories", {}).items():
                for stat in cat_stats:
                    key = f"{period_name}_{cat_name}_{stat['name']}"
                    flat_stats[key] = {
                        "home": stat["home"],
                        "away": stat["away"],
                    }
    
    if not flat_stats:
        return
    
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO match_stats (match_id, stats_json, fetched_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(match_id) DO UPDATE SET
                stats_json = excluded.stats_json,
                fetched_at = excluded.fetched_at
            """,
            (match_id, json.dumps(flat_stats, ensure_ascii=False)),
        )
        conn.commit()


def get_match_stats(match_id: str) -> Dict[str, Any] | None:
    """Получение сохранённой статистики матча."""
    from db import get_db_connection
    
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT stats_json FROM match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        
        if not row:
            return None
        
        import json
        try:
            return json.loads(row["stats_json"])
        except (json.JSONDecodeError, TypeError):
            return None
