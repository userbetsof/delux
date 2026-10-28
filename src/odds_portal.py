"""Парсинг истории движения коэффициентов с Oddsportal.com.

Извлекает историю изменения кф по букмекерам для анализа line movement,
value betting opportunities и реакции рынка.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import urllib.request
import urllib.error
import json
import random

# Rate limiting
_MIN_REQUEST_DELAY = 1.0  # секунд между запросами
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0

# User-Agent для обхода Cloudflare
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def _fetch_oddsportal(url: str, retries: int = _MAX_RETRIES) -> Optional[str]:
    """GET запрос к Oddsportal с retry и rate limiting."""
    last_err: Optional[Exception] = None
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": _random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": "https://www.oddsportal.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_err = exc
            if attempt < retries - 1:
                delay = _RETRY_DELAY * (attempt + 1) + random.uniform(0, 1)
                print(f"  [!] Oddsportal retry {attempt + 1}/{retries} in {delay:.1f}s: {exc}")
                time.sleep(delay)
    
    if last_err:
        print(f"  [!] Oddsportal fetch failed: {last_err}")
    return None


def _parse_odds_table(html: str) -> List[Dict[str, Any]]:
    """Парсит таблицу коэффициентов из HTML Oddsportal.
    
    Извлекает: bookmaker, market (1X2/OU/BTTS), outcome, odds, timestamp.
    """
    results: List[Dict[str, Any]] = []
    
    # Ищем блоки с данными букмекеров
    # Паттерн: data-bookmaker="Bet365" или <td class="bookname">Bet365</td>
    bookmaker_re = re.compile(r'(?:data-bookmaker="([^"]+)"|class="bookname"[^>]*>)([^<]+)')
    
    # Паттерн для market: 1X2, Over/Under, BTTS
    market_re = re.compile(r'(1X2|1X2\+OU|OU|OU\+1X2|BTTS|O/U|1\X2|Over/Under)', re.I)
    
    # Паттерн для коэффициентов: <td class="odds">2.10</td> или data-odd="2.10"
    odd_re = re.compile(r'(?:data-odd="([^"]+)"|class="odds[^"]*">([^<]+))')
    
    # Паттерн для outcome: 1, X, 2, Over, Under
    outcome_re = re.compile(r'(?:data-outcome="([^"]+)"|class="odd[^"]*">(1|X|2|Over|Under))', re.I)
    
    # Парсим по строкам таблицы
    lines = html.split("\n")
    current_bookmaker = ""
    current_market = "1X2"
    
    for line in lines:
        # Извлекаем bookmaker
        bm_match = bookmaker_re.search(line)
        if bm_match:
            current_bookmaker = bm_match.group(2).strip()
            continue
        
        # Извлекаем market
        mkt_match = market_re.search(line)
        if mkt_match:
            mkt = mkt_match.group(1).strip()
            if "OU" in mkt.upper() or "O/U" in mkt.upper():
                current_market = "Over/Under"
            elif "BTTS" in mkt.upper():
                current_market = "BTTS"
            else:
                current_market = "1X2"
            continue
        
        # Извлекаем коэффициенты
        if current_bookmaker:
            odd_matches = odd_re.findall(line)
            outcome_matches = outcome_re.findall(line)
            
            for odd_val, odd_text in odd_matches:
                value = odd_val or odd_text
                if not value or not value.replace(".", "").replace(",", "").isdigit():
                    continue
                
                # Определяем outcome по позиции
                outcome = ""
                if outcome_matches:
                    for om in outcome_matches:
                        if om[0]:  # data-outcome
                            outcome = om[0]
                        elif om[1]:  # class="odd">1/X/2
                            outcome = om[1]
                        else:
                            break
                
                # Если outcome не определён, используем дефолтные
                if not outcome:
                    # Простая эвристика: первый = 1, второй = X, третий = 2
                    pass
                
                results.append({
                    "bookmaker": current_bookmaker,
                    "market": current_market,
                    "outcome": outcome,
                    "odds_value": float(value),
                })
    
    return results


def _parse_historical_odds(html: str) -> List[Dict[str, Any]]:
    """Парсит историю изменения коэффициентов из HTML.
    
    Ищем блоки с timestamp и старыми коэффициентами.
    """
    results: List[Dict[str, Any]] = []
    
    # Паттерн для timestamp: 15.01.2024 14:30 или similar
    timestamp_re = re.compile(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})')
    
    # Паттерн для old odds: <span class="odd-old">2.50</span>
    old_odd_re = re.compile(r'(?:class="odd-old[^"]*">|data-old-odd=")([^<"]+)')
    
    lines = html.split("\n")
    current_timestamp = ""
    
    for line in lines:
        ts_match = timestamp_re.search(line)
        if ts_match:
            current_timestamp = ts_match.group(1)
            continue
        
        if current_timestamp:
            old_match = old_odd_re.search(line)
            if old_match:
                value = old_match.group(1)
                try:
                    odds_val = float(value.replace(",", "."))
                    results.append({
                        "odds_value": odds_val,
                        "odds_timestamp": current_timestamp,
                    })
                except ValueError:
                    pass
    
    return results


def fetch_odds_history(match_id: str) -> List[Dict[str, Any]]:
    """Загрузка истории коэффициентов для одного матча.
    
    Args:
        match_id: Flashscore match ID (используется как часть URL)
    
    Returns:
        Список словарей с историей коэффициентов
    """
    # URL Oddsportal: https://www.oddsportal.com/match/{match_id}/odds/
    url = f"https://www.oddsportal.com/match/{match_id}/odds/#odds-overunder;1"
    
    print(f"  [FETCH] Oddsportal: {url}")
    html = _fetch_oddsportal(url)
    if not html:
        return []
    
    # Парсим текущие коэффициенты
    current = _parse_odds_table(html)
    
    # Парсим исторические данные (если есть)
    historical = _parse_historical_odds(html)
    
    # Добавляем timestamp для текущих
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    for item in current:
        item["odds_timestamp"] = now
        item["odds_source"] = "scraped"
    
    all_odds = current + historical
    
    print(f"  [OK] Извлечено {len(all_odds)} записей (текущие: {len(current)}, история: {len(historical)})")
    return all_odds


def fetch_odds_history_batch(match_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Пакетная загрузка истории коэффициентов.
    
    Args:
        match_ids: Список match_id
    
    Returns:
        Словарь {match_id: [odds_records]}
    """
    results: Dict[str, List[Dict[str, Any]]] = {}
    
    for i, match_id in enumerate(match_ids):
        print(f"\n[{i + 1}/{len(match_ids)}] {match_id}")
        odds = fetch_odds_history(match_id)
        if odds:
            results[match_id] = odds
        
        # Rate limiting
        if i < len(match_ids) - 1:
            delay = _MIN_REQUEST_DELAY + random.uniform(0, 0.5)
            time.sleep(delay)
    
    print(f"\n[SUMMARY] Загружено {len(results)}/{len(match_ids)} матчей")
    return results


def get_line_movement(match_id: str) -> Dict[str, Any]:
    """Анализ движения линии для матча.
    
    Args:
        match_id: Flashscore match ID
    
    Returns:
        Словарь с анализом line movement
    """
    odds = fetch_odds_history(match_id)
    if not odds:
        return {}
    
    # Группируем по bookmaker + market
    by_bookmaker_market: Dict[str, List[Dict[str, Any]]] = {}
    for item in odds:
        key = f"{item['bookmaker']}_{item['market']}"
        by_bookmaker_market.setdefault(key, []).append(item)
    
    movement: Dict[str, Any] = {
        "match_id": match_id,
        "total_records": len(odds),
        "bookmakers": list(set(o["bookmaker"] for o in odds)),
        "markets": list(set(o["market"] for o in odds)),
        "by_bookmaker_market": {},
    }
    
    for key, items in by_bookmaker_market.items():
        # Сортируем по timestamp
        items.sort(key=lambda x: x.get("odds_timestamp", ""))
        
        if len(items) < 2:
            movement["by_bookmaker_market"][key] = {
                "records": 1,
                "first_odds": items[0]["odds_value"],
                "last_odds": items[0]["odds_value"],
                "change": 0,
                "change_pct": 0,
            }
            continue
        
        first = items[0]["odds_value"]
        last = items[-1]["odds_value"]
        change = last - first
        change_pct = (change / first * 100) if first > 0 else 0
        
        # Находим пик и минимум
        max_odd = max(o["odds_value"] for o in items)
        min_odd = min(o["odds_value"] for o in items)
        
        movement["by_bookmaker_market"][key] = {
            "records": len(items),
            "first_odds": first,
            "last_odds": last,
            "change": round(change, 3),
            "change_pct": round(change_pct, 2),
            "max_odds": max_odd,
            "min_odds": min_odd,
            "volatility": round(max_odd - min_odd, 3),
        }
    
    return movement


def detect_value_opportunities(match_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Поиск value betting возможностей (расхождения между БК).
    
    Args:
        match_ids: Список match_id (или все матчи с odds_history)
    
    Returns:
        Список value opportunities
    """
    from db import get_db_connection
    
    opportunities: List[Dict[str, Any]] = []
    
    with get_db_connection() as conn:
        if match_ids:
            placeholders = ",".join(["?"] * len(match_ids))
            query = f"""
                SELECT DISTINCT match_id, bookmaker, market, outcome, odds_value
                FROM odds_history
                WHERE match_id IN ({placeholders})
                ORDER BY match_id, bookmaker
            """
            rows = conn.execute(query, match_ids).fetchall()
        else:
            query = """
                SELECT DISTINCT match_id, bookmaker, market, outcome, odds_value
                FROM odds_history
                ORDER BY match_id, bookmaker
            """
            rows = conn.execute(query).fetchall()
    
    # Группируем по match_id + market + outcome
    by_match: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = f"{row['match_id']}_{row['market']}_{row['outcome']}"
        by_match.setdefault(key, []).append({
            "match_id": row["match_id"],
            "bookmaker": row["bookmaker"],
            "market": row["market"],
            "outcome": row["outcome"],
            "odds_value": row["odds_value"],
        })
    
    for key, items in by_match.items():
        if len(items) < 2:
            continue
        
        odds_values = [item["odds_value"] for item in items if item["odds_value"] > 0]
        if not odds_values:
            continue
        
        max_odds = max(odds_values)
        min_odds = min(odds_values)
        avg_odds = sum(odds_values) / len(odds_values)
        
        # Ищем расхождения > 5%
        spread_pct = ((max_odds - min_odds) / min_odds * 100) if min_odds > 0 else 0
        if spread_pct >= 5.0:
            opportunities.append({
                "match_id": items[0]["match_id"],
                "market": items[0]["market"],
                "outcome": items[0]["outcome"],
                "max_odds": max_odds,
                "min_odds": min_odds,
                "avg_odds": round(avg_odds, 3),
                "spread_pct": round(spread_pct, 2),
                "bookmakers": [item["bookmaker"] for item in items],
            })
    
    # Сортируем по spread (убывание)
    opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
    
    print(f"[VALUE] Найдено {len(opportunities)} opportunities со spread >= 5%")
    return opportunities


def save_odds_history(match_id: str, odds_records: List[Dict[str, Any]]) -> int:
    """Сохраняет историю коэффициентов в БД.
    
    Args:
        match_id: Flashscore match ID
        odds_records: Список записей с полями bookmaker, market, outcome, odds_value, odds_timestamp
    
    Returns:
        Количество сохранённых записей
    """
    from db import get_db_connection
    
    saved = 0
    with get_db_connection() as conn:
        for record in odds_records:
            conn.execute(
                """
                INSERT OR IGNORE INTO odds_history 
                (match_id, bookmaker, market, outcome, odds_value, odds_timestamp, odds_source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    record.get("bookmaker", ""),
                    record.get("market", "1X2"),
                    record.get("outcome", ""),
                    record.get("odds_value"),
                    record.get("odds_timestamp", datetime.now().strftime("%d.%m.%Y %H:%M")),
                    record.get("odds_source", "scraped"),
                ),
            )
            saved += conn.total_changes
    
    conn.commit()
    print(f"  [DB] Сохранено {saved} записей для {match_id}")
    return saved


def main():
    """CLI для тестирования."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Oddsportal history scraper")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # fetch
    p_fetch = sub.add_parser("fetch", help="Загрузка истории для матча")
    p_fetch.add_argument("--match-id", required=True, help="Flashscore match ID")
    
    # batch
    p_batch = sub.add_parser("batch", help="Пакетная загрузка")
    p_batch.add_argument("--match-ids", nargs="+", help="Список match ID")
    p_batch.add_argument("--file", help="Файл со списком match ID (по одному на строку)")
    
    # analyze
    p_analyze = sub.add_parser("analyze", help="Анализ line movement")
    p_analyze.add_argument("--match-id", required=True, help="Flashscore match ID")
    
    # value
    p_value = sub.add_parser("value", help="Поиск value opportunities")
    p_value.add_argument("--match-ids", nargs="+", help="Ограничить список матчей")
    
    args = parser.parse_args()
    
    if args.command == "fetch":
        odds = fetch_odds_history(args.match_id)
        print(f"\n[RESULT] {len(odds)} записей")
        for o in odds[:10]:
            print(f"  {o['bookmaker']:20} {o['market']:15} {o['outcome']:5} {o['odds_value']:.2f} @ {o.get('odds_timestamp', '')}")
    
    elif args.command == "batch":
        match_ids = args.match_ids or []
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                match_ids = [line.strip() for line in f if line.strip()]
        
        results = fetch_odds_history_batch(match_ids)
        print(f"\n[RESULT] Всего {sum(len(v) for v in results.values())} записей")
    
    elif args.command == "analyze":
        movement = get_line_movement(args.match_id)
        if movement:
            print(f"\n[LINE MOVEMENT] {args.match_id}")
            print(f"  Bookmakers: {', '.join(movement['bookmakers'])}")
            print(f"  Markets: {', '.join(movement['markets'])}")
            for key, data in movement["by_bookmaker_market"].items():
                print(f"  {key}: {data['first_odds']:.2f} → {data['last_odds']:.2f} ({data['change_pct']:+.2f}%)")
    
    elif args.command == "value":
        opportunities = detect_value_opportunities(args.match_ids)
        if opportunities:
            print(f"\n[VALUE OPPORTUNITIES]")
            for opp in opportunities[:20]:
                print(f"  {opp['match_id']} | {opp['market']} {opp['outcome']} | "
                      f"{opp['bookmakers']} | {opp['min_odds']:.2f} - {opp['max_odds']:.2f} ({opp['spread_pct']:.1f}%)")


if __name__ == "__main__":
    main()
