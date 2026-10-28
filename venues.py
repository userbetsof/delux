"""Управление стадионами и расчёт расстояний.

Функции:
1. Загрузка координат стадионов (из match_snapshot или geocoding)
2. Массовый расчёт расстояний между всеми парами стадионов
3. Добавление distance как фичи в XGBoost
4. Анализ влияния расстояния на результаты матчей
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from db import (
    get_db_connection,
    get_cached_venue,
    upsert_venue,
    calculate_and_save_venue_distance,
    get_venue_distance,
    haversine_distance,
    calculate_team_home_stadium,
)


# ============================================================================
# ГЕОКОДИНГ — получение координат по названию стадиона/города
# ============================================================================

# Базовые координаты городов (для быстрого старта)
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # Россия
    "Москва": (55.7558, 37.6173),
    "Санкт-Петербург": (59.9343, 30.3351),
    "Казань": (55.7892, 49.1233),
    "Нижний Новгород": (56.2965, 43.9361),
    "Самара": (53.1959, 50.1002),
    "Волгоград": (48.7080, 44.5133),
    "Ростов-на-Дону": (47.2357, 39.7015),
    "Саратов": (51.5462, 46.0154),
    "Сочи": (43.5855, 39.7231),
    "Екатеринбург": (56.8389, 60.6057),
    "Краснодар": (45.0355, 38.9753),
    "Тула": (54.1931, 37.6182),
    "Воронеж": (51.6683, 39.1844),
    "Астрахань": (46.3479, 48.0336),
    "Уфа": (54.7388, 55.9721),
    "Пермь": (58.0105, 56.2294),
    "Красноярск": (52.2871, 92.8668),
    "Владивосток": (43.1155, 131.8855),
    "Новосибирск": (55.0084, 82.9357),
    "Тюмень": (57.1553, 65.5619),
    # Европа
    "Лондон": (51.5074, -0.1278),
    "Манчестер": (53.4808, -2.2426),
    "Ливерпуль": (53.4084, -2.9916),
    "Бирмингем": (52.4862, -1.8904),
    "Берлин": (52.5200, 13.4050),
    "Мюнхен": (48.1351, 11.5820),
    "Гамбург": (53.5511, 9.9937),
    "Дортмунд": (51.5136, 7.4653),
    "Франкфурт": (50.1109, 8.6821),
    "Париж": (48.8566, 2.3522),
    "Марсель": (43.2965, 5.3698),
    "Лион": (45.7640, 4.8357),
    "Мадрид": (40.4168, -3.7038),
    "Барселона": (41.3874, 2.1686),
    "Милан": (45.4642, 9.1900),
    "Рим": (41.9028, 12.4964),
    "Турин": (45.0703, 7.6869),
    # Америка
    "Нью-Йорк": (40.7128, -74.0060),
    "Лос-Анджелес": (34.0522, -118.2437),
    "Чикаго": (41.8781, -87.6298),
    "Мехико": (19.4326, -99.1332),
    "Буэнос-Айрес": (-34.6037, -58.3816),
    "Сан-Паулу": (-23.5505, -46.6333),
    "Рио-де-Жанейро": (-22.9068, -43.1729),
}


def geocode_venue(venue: str, town: str) -> Optional[Dict[str, float]]:
    """Получить координаты стадиона по названию и городу.
    
    Приоритет:
    1. Точное совпадение в CITY_COORDS
    2. Geocoding API (Nominatim/OpenStreetMap) — бесплатный, без ключа
    3. Возвращает None если не найдено
    """
    # Проверяем базовые координаты
    town_key = town.strip()
    if town_key in CITY_COORDS:
        lat, lon = CITY_COORDS[town_key]
        return {"latitude": lat, "longitude": lon}
    
    # Пробуем по названию стадиона
    venue_key = f"{venue}, {town}"
    for key, coords in CITY_COORDS.items():
        if key.lower() in venue_key.lower() or venue_key.lower().startswith(key.lower()):
            lat, lon = coords
            return {"latitude": lat, "longitude": lon}
    
    # Geocoding через Nominatim (OpenStreetMap)
    try:
        import urllib.request
        import json
        
        query = f"{venue}, {town}"
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(query)}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "DeluX/1.0"})
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        if data:
            return {
                "latitude": float(data[0]["lat"]),
                "longitude": float(data[0]["lon"]),
            }
    except Exception as e:
        print(f"  [WARN] Geocoding failed for '{venue}, {town}': {e}")
    
    return None


# ============================================================================
# ЗАГРУЗКА СТАДИОНОВ ИЗ БД
# ============================================================================

def load_venues_from_snapshots() -> List[Dict[str, str]]:
    """Загружает уникальные пары (стадион, город) из match_snapshot."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT venue, town
            FROM match_snapshot
            WHERE venue IS NOT NULL AND venue != ''
              AND town IS NOT NULL AND town != ''
            ORDER BY venue
            """
        ).fetchall()
        
        venues = []
        for row in rows:
            venues.append({
                "venue": row["venue"].strip(),
                "town": row["town"].strip(),
            })
        
        return venues


def get_all_venues() -> List[Dict[str, Any]]:
    """Получает все стадионы из БД с координатами."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, venue, town, latitude, longitude, source, updated_at
            FROM venues
            ORDER BY venue
            """
        ).fetchall()
        
        return [dict(row) for row in rows]


def load_venues_to_geocode() -> List[Dict[str, str]]:
    """Находит стадионы без координат для геокодирования."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT venue, town
            FROM venues
            WHERE latitude IS NULL OR longitude IS NULL
            ORDER BY venue
            """
        ).fetchall()
        
        return [{"venue": row["venue"], "town": row["town"]} for row in rows]


# ============================================================================
# ГЕОКОДИРОВАНИЕ И СОХРАНЕНИЕ
# ============================================================================

def geocode_and_save_venues(batch_size: int = 50) -> Dict[str, int]:
    """Геокодирует стадионы без координат и сохраняет в БД.
    
    Возвращает: {"geocoded": N, "failed": N, "skipped": N}
    """
    venues_to_geocode = load_venues_to_geocode()
    
    if not venues_to_geocode:
        print("[INFO] Все стадионы уже имеют координаты")
        return {"geocoded": 0, "failed": 0, "skipped": 0}
    
    print(f"\n[GEOLocate] Found {len(venues_to_geocode)} venues without coordinates")
    print(f"{'='*60}")
    
    stats = {"geocoded": 0, "failed": 0, "skipped": 0}
    
    for i, venue in enumerate(venues_to_geocode, 1):
        print(f"[{i}/{len(venues_to_geocode)}] {venue['venue']}, {venue['town']}...", end=" ")
        
        coords = geocode_venue(venue["venue"], venue["town"])
        
        if coords:
            upsert_venue(venue["venue"], venue["town"], coords)
            print(f"✅ ({coords['latitude']:.4f}, {coords['longitude']:.4f})")
            stats["geocoded"] += 1
        else:
            print("❌ Failed")
            stats["failed"] += 1
        
        # Пауза между запросами к Nominatim (1 req/sec limit)
        if i % batch_size == 0:
            print(f"  [INFO] Batch completed, waiting 1 second...")
            import time
            time.sleep(1)
    
    print(f"\n[GEOLocate] Results: {stats['geocoded']} geocoded, {stats['failed']} failed")
    return stats


# ============================================================================
# РАСЧЁТ РАССТОЯНИЙ
# ============================================================================

def calculate_all_distances() -> Dict[str, int]:
    """Массовый расчёт расстояний между всеми парами стадионов.
    
    Возвращает: {"calculated": N, "skipped": N, "failed": N}
    """
    venues = get_all_venues()
    
    venues_with_coords = [v for v in venues if v.get("latitude") and v.get("longitude")]
    
    if len(venues_with_coords) < 2:
        print("[INFO] Need at least 2 venues with coordinates")
        return {"calculated": 0, "skipped": 0, "failed": 0}
    
    print(f"\n[DISTANCE] Calculating distances for {len(venues_with_coords)} venues")
    print(f"[DISTANCE] Total pairs: {len(venues_with_coords) * (len(venues_with_coords) - 1) // 2}")
    print(f"{'='*60}")
    
    stats = {"calculated": 0, "skipped": 0, "failed": 0}
    total_pairs = 0
    
    for i, home in enumerate(venues_with_coords):
        for away in venues_with_coords[i + 1:]:
            total_pairs += 1
            
            home_venue = home["venue"]
            home_town = home["town"]
            away_venue = away["venue"]
            away_town = away["town"]
            
            # Проверяем кэш
            cached = get_venue_distance(home_venue, home_town, away_venue, away_town)
            if cached is not None:
                stats["skipped"] += 1
                continue
            
            # Рассчитываем расстояние
            try:
                distance = haversine_distance(
                    home["latitude"], home["longitude"],
                    away["latitude"], away["longitude"]
                )
                
                # Сохраняем в обоих направлениях
                from db import upsert_venue_distance
                with get_db_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO venue_distances 
                        (home_venue, home_town, away_venue, away_town, distance_km)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (home_venue, home_town, away_venue, away_town, distance)
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO venue_distances 
                        (home_venue, home_town, away_venue, away_town, distance_km)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (away_venue, away_town, home_venue, home_town, distance)
                    )
                    conn.commit()
                
                stats["calculated"] += 1
                
                # Прогресс
                if total_pairs % 100 == 0:
                    print(f"  [INFO] Progress: {total_pairs} pairs processed, {stats['calculated']} calculated")
                    
            except Exception as e:
                stats["failed"] += 1
                print(f"  [ERROR] Failed for {home_venue} - {away_venue}: {e}")
    
    print(f"\n[DISTANCE] Results:")
    print(f"  Calculated: {stats['calculated']}")
    print(f"  Skipped (cached): {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")
    
    return stats


def get_team_home_venue(team_name: str) -> Optional[Tuple[str, str]]:
    """Определяет домашний стадион команды из истории матчей."""
    from db import get_db_connection
    
    with get_db_connection() as conn:
        # Ищем матчи где команда играла дома
        rows = conn.execute(
            """
            SELECT ms.venue, ms.town, COUNT(*) as cnt
            FROM matches m
            JOIN match_snapshot ms ON ms.match_id = m.match_id
            WHERE m.home_team_id = (
                SELECT id FROM teams WHERE name = ? COLLATE NOCASE
            )
            AND ms.venue IS NOT NULL AND ms.town IS NOT NULL
            GROUP BY ms.venue, ms.town
            ORDER BY cnt DESC
            LIMIT 1
            """,
            ((team_name or "").strip(),)
        ).fetchall()
        
        if rows:
            return (rows[0]["venue"].strip(), rows[0]["town"].strip())
        return None


def populate_match_distances(match_ids: Optional[List[str]] = None) -> int:
    """Заполняет match_snapshot.distance для матчей.
    
    Определяет home/away стадионы для каждой команды из истории матчей.
    
    Args:
        match_ids: список match_id для расчёта (или все матчи)
    
    Returns:
        Количество обработанных матчей
    """
    with get_db_connection() as conn:
        if match_ids:
            placeholders = ",".join(["?"] * len(match_ids))
            query = f"""
                SELECT m.match_id, m.home_team_id, m.away_team_id,
                       ms.venue, ms.town
                FROM matches m
                JOIN match_snapshot ms ON ms.match_id = m.match_id
                WHERE m.match_id IN ({placeholders})
            """
            rows = conn.execute(query, match_ids).fetchall()
        else:
            query = """
                SELECT m.match_id, m.home_team_id, m.away_team_id,
                       ms.venue, ms.town
                FROM matches m
                JOIN match_snapshot ms ON ms.match_id = m.match_id
            """
            rows = conn.execute(query).fetchall()
        
        count = 0
        skipped = 0
        
        # Кэш для home venue команд
        team_venue_cache: Dict[str, Tuple[str, str]] = {}
        
        for row in rows:
            match_id = row["match_id"]
            home_team_id = row["home_team_id"]
            away_team_id = row["away_team_id"]
            
            # Получаем названия команд
            home_team_row = conn.execute(
                "SELECT name FROM teams WHERE id = ?", (home_team_id,)
            ).fetchone()
            away_team_row = conn.execute(
                "SELECT name FROM teams WHERE id = ?", (away_team_id,)
            ).fetchone()
            
            if not home_team_row or not away_team_row:
                skipped += 1
                continue
            
            home_team_name = home_team_row["name"]
            away_team_name = away_team_row["name"]
            
            # Определяем home venue для домашней команды
            if home_team_name not in team_venue_cache:
                team_venue_cache[home_team_name] = get_team_home_venue(home_team_name)
            home_venue_data = team_venue_cache[home_team_name]
            
            # Определяем home venue для гостевой команды
            if away_team_name not in team_venue_cache:
                team_venue_cache[away_team_name] = get_team_home_venue(away_team_name)
            away_venue_data = team_venue_cache[away_team_name]
            
            if not home_venue_data or not away_venue_data:
                skipped += 1
                continue
            
            home_venue, home_town = home_venue_data
            away_venue, away_town = away_venue_data
            
            # Рассчитываем расстояние
            distance = get_venue_distance(home_venue, home_town, away_venue, away_town)
            if distance is not None:
                conn.execute(
                    "UPDATE match_snapshot SET distance = ? WHERE match_id = ?",
                    (distance, match_id)
                )
                count += 1
            else:
                skipped += 1
        
        conn.commit()
        print(f"[DISTANCE] Match distances: {count} calculated, {skipped} skipped")
        return count


# ============================================================================
# ДОБАВЛЕНИЕ DISTANCE В XGBOOST FEATURES
# ============================================================================

def add_distance_to_features() -> None:
    """Добавляет distance как фичу в XGBoost.
    
    Проверяет, что distance уже заполнен в match_snapshot.
    Если нет — запускает populate_match_distances.
    """
    print("\n[FEATURE] Checking distance in match_snapshot...")
    
    with get_db_connection() as conn:
        # Проверяем сколько матчей уже имеют distance
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM match_snapshot
            WHERE distance IS NOT NULL AND distance > 0
            """
        ).fetchone()
        
        count_with_distance = row["cnt"] if row else 0
        
        if count_with_distance == 0:
            print("[FEATURE] No distances found. Running populate...")
            populate_match_distances()
            
            # Проверяем снова
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM match_snapshot
                WHERE distance IS NOT NULL AND distance > 0
                """
            ).fetchone()
            count_with_distance = row["cnt"] if row else 0
        
        print(f"[FEATURE] {count_with_distance} matches have distance_km feature")
        print(f"[FEATURE] distance_km будет включён в XGBoost автоматически")


# ============================================================================
# АНАЛИЗ ВЛИЯНИЯ РАССТОЯНИЯ
# ============================================================================

def analyze_distance_impact() -> Dict[str, Any]:
    """Анализирует влияние расстояния на результаты матчей.
    
    Возвращает статистику:
    - Корреляция distance vs home_win_rate
    - Разбивка по дистанциям (0-50km, 50-200km, 200-500km, 500km+)
    - Средние голы хозяев/гостей по дистанциям
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.match_id, m.score_home, m.score_away,
                   ms.distance,
                   CASE WHEN m.score_home > m.score_away THEN 1
                        WHEN m.score_home = m.score_away THEN 0
                        ELSE -1 END as result
            FROM matches m
            JOIN match_snapshot ms ON ms.match_id = m.match_id
            WHERE m.match_status = 'Завершен'
              AND ms.distance IS NOT NULL AND ms.distance > 0
              AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
            ORDER BY ms.distance
            """
        ).fetchall()
        
        # Если нет данных с distance — пробуем рассчитать
        if not rows:
            print("[ANALYSIS] No matches with distance data. Running populate...")
            populate_match_distances()
            rows = conn.execute(
                """
                SELECT m.match_id, m.score_home, m.score_away,
                       ms.distance,
                       CASE WHEN m.score_home > m.score_away THEN 1
                            WHEN m.score_home = m.score_away THEN 0
                            ELSE -1 END as result
                FROM matches m
                JOIN match_snapshot ms ON ms.match_id = m.match_id
                WHERE m.match_status = 'Завершен'
                  AND ms.distance IS NOT NULL AND ms.distance > 0
                  AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
                ORDER BY ms.distance
                """
            ).fetchall()
        
        if not rows:
            print("[ANALYSIS] No matches with distance data")
            return {}
        
        # Разбивка по дистанциям
        buckets = {
            "0-50km": {"count": 0, "home_wins": 0, "draws": 0, "away_wins": 0, "home_goals": 0, "away_goals": 0},
            "50-200km": {"count": 0, "home_wins": 0, "draws": 0, "away_wins": 0, "home_goals": 0, "away_goals": 0},
            "200-500km": {"count": 0, "home_wins": 0, "draws": 0, "away_wins": 0, "home_goals": 0, "away_goals": 0},
            "500km+": {"count": 0, "home_wins": 0, "draws": 0, "away_wins": 0, "home_goals": 0, "away_goals": 0},
        }
        
        distances = []
        home_win_rates = []
        
        for row in rows:
            dist = row["distance"]
            result = row["result"]
            
            # Определяем bucket
            if dist <= 50:
                bucket = "0-50km"
            elif dist <= 200:
                bucket = "50-200km"
            elif dist <= 500:
                bucket = "200-500km"
            else:
                bucket = "500km+"
            
            bucket_data = buckets[bucket]
            bucket_data["count"] += 1
            bucket_data["home_goals"] += row["score_home"]
            bucket_data["away_goals"] += row["score_away"]
            
            if result == 1:
                bucket_data["home_wins"] += 1
            elif result == 0:
                bucket_data["draws"] += 1
            else:
                bucket_data["away_wins"] += 1
            
            distances.append(dist)
            home_win_rates.append(1 if result == 1 else 0)
        
        # Корреляция Пирсона
        n = len(distances)
        mean_d = sum(distances) / n
        mean_h = sum(home_win_rates) / n
        
        numerator = sum((d - mean_d) * (h - mean_h) for d, h in zip(distances, home_win_rates))
        denom_d = math.sqrt(sum((d - mean_d) ** 2 for d in distances))
        denom_h = math.sqrt(sum((h - mean_h) ** 2 for h in home_win_rates))
        
        correlation = numerator / (denom_d * denom_h) if (denom_d * denom_h) > 0 else 0
        
        # Форматируем результаты
        results = {}
        for bucket_name, data in buckets.items():
            if data["count"] > 0:
                results[bucket_name] = {
                    "matches": data["count"],
                    "home_win_rate": round(data["home_wins"] / data["count"], 3),
                    "draw_rate": round(data["draws"] / data["count"], 3),
                    "away_win_rate": round(data["away_wins"] / data["count"], 3),
                    "avg_home_goals": round(data["home_goals"] / data["count"], 2),
                    "avg_away_goals": round(data["away_goals"] / data["count"], 2),
                }
        
        results["correlation"] = round(correlation, 3)
        results["total_matches"] = n
        results["avg_distance"] = round(sum(distances) / n, 1) if n > 0 else 0
        
        return results


def print_distance_analysis(analysis: Dict[str, Any]) -> None:
    """Выводит результаты анализа расстояний."""
    if not analysis:
        print("[ANALYSIS] No data to display")
        return
    
    print(f"\n{'='*60}")
    print("[ANALYSIS] Distance Impact on Match Results")
    print(f"{'='*60}")
    print(f"Total matches: {analysis.get('total_matches', 0)}")
    print(f"Avg distance: {analysis.get('avg_distance', 0)} km")
    print(f"Correlation (distance vs home_win): {analysis.get('correlation', 0)}")
    print(f"\n{'Bucket':<15} {'Matches':<10} {'Home Win%':<12} {'Draw%':<10} {'Away Win%':<12} {'HG':<6} {'AG':<6}")
    print("-" * 60)
    
    for bucket_name in ["0-50km", "50-200km", "200-500km", "500km+"]:
        if bucket_name in analysis:
            data = analysis[bucket_name]
            print(f"{bucket_name:<15} {data['matches']:<10} {data['home_win_rate']*100:<12.1f} "
                  f"{data['draw_rate']*100:<10.1f} {data['away_win_rate']*100:<12.1f} "
                  f"{data['avg_home_goals']:<6.2f} {data['avg_away_goals']:<6.2f}")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Управление стадионами и расчёт расстояний",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    
    # geocode
    p_geo = sub.add_parser("geocode", help="Геокодирование стадионов без координат")
    p_geo.add_argument("--batch", type=int, default=50, help="Размер батча (по умолчанию: 50)")
    
    # distances
    p_dist = sub.add_parser("distances", help="Расчёт всех расстояний между стадионами")
    
    # analysis
    p_ana = sub.add_parser("analysis", help="Анализ влияния расстояния на результаты")
    
    # match-distances
    p_match = sub.add_parser("match-distances", help="Заполнить distance для матчей")
    p_match.add_argument("--match-id", default="", help="Конкретный match_id (опционально)")
    
    # all-in-one
    p_all = sub.add_parser("all", help="Геокодирование + расчёт расстояний + анализ")
    
    args = parser.parse_args()
    
    if args.command == "geocode":
        stats = geocode_and_save_venues(args.batch)
        print(f"\n[RESULT] Geocoding: {stats['geocoded']} geocoded, {stats['failed']} failed")
    
    elif args.command == "distances":
        stats = calculate_all_distances()
        print(f"\n[RESULT] Distances: {stats['calculated']} calculated, {stats['skipped']} skipped")
    
    elif args.command == "match-distances":
        match_ids = [args.match_id] if args.match_id else None
        count = populate_match_distances(match_ids)
        print(f"\n[RESULT] Match distances: {count} populated")
    
    elif args.command == "analysis":
        analysis = analyze_distance_impact()
        print_distance_analysis(analysis)
    
    elif args.command == "all":
        print("\n" + "="*60)
        print("[STEP 1] Geocoding venues...")
        print("="*60)
        geo_stats = geocode_and_save_venues()
        
        print("\n" + "="*60)
        print("[STEP 2] Calculating distances...")
        print("="*60)
        dist_stats = calculate_all_distances()
        
        print("\n" + "="*60)
        print("[STEP 3] Analyzing distance impact...")
        print("="*60)
        analysis = analyze_distance_impact()
        print_distance_analysis(analysis)
        
        print(f"\n{'='*60}")
        print("[COMPLETE]")
        print(f"{'='*60}")
        print(f"Geocoded: {geo_stats['geocoded']}")
        print(f"Distances calculated: {dist_stats['calculated']}")


if __name__ == "__main__":
    main()
