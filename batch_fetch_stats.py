"""Пакетная загрузка статистики матчей из Flashscore."""

from __future__ import annotations

import random
import sys
import time
from datetime import datetime

sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection
from match_stats import fetch_match_stats, save_match_stats


def batch_fetch_match_stats(
    limit: int = 0,
    offset: int = 0,
    delay: float = 1.5,
    sport: int = 1,
) -> dict:
    """Пакетная загрузка статистики для матчей."""
    summary = {
        "total": 0,
        "fetched": 0,
        "saved": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    # Получаем список матчей БЕЗ статистики
    query = """
        SELECT m.match_id, m.match_date, t1.name as home, t2.name as away
        FROM matches m
        JOIN teams t1 ON t1.id = m.home_team_id
        JOIN teams t2 ON t2.id = m.away_team_id
        WHERE m.sport = ?
          AND m.match_id NOT IN (SELECT match_id FROM match_stats)
        ORDER BY m.match_date DESC
        LIMIT ? OFFSET ?
    """
    
    params: list = [sport, limit if limit > 0 else -1, offset]
    
    with get_db_connection() as conn:
        matches = conn.execute(query, params).fetchall()
        summary["total"] = len(matches)
        
        print(f"[+] Found {len(matches)} football matches to fetch stats for")
        print(f"[+] Starting batch fetch (delay={delay}s)...\n")
        
        for i, match in enumerate(matches, 1):
            match_id, match_date, home, away = match
            
            # Проверяем, есть ли уже статистика
            existing = conn.execute(
                "SELECT COUNT(*) FROM match_stats WHERE match_id = ?",
                (match_id,),
            ).fetchone()[0]
            
            if existing > 0:
                summary["skipped"] += 1
                print(f"  [{i}/{len(matches)}] SKIP {match_id} {home} vs {away} (already has stats)")
                continue
            
            # Пытаемся загрузить статистику
            try:
                stats = fetch_match_stats(match_id, sport=sport)
                
                if stats:
                    save_match_stats(match_id, stats)
                    summary["fetched"] += 1
                    summary["saved"] += 1
                    
                    # Выводим основную статистику
                    match_data = stats.get("match", {})
                    if match_data:
                        shots = match_data.get("Главное_Удары в створ", {})
                        if shots:
                            print(
                                f"  [{i}/{len(matches)}] OK {match_id} {home} vs {away} "
                                f"| удары в створ: {shots.get('home', 0)}:{shots.get('away', 0)}"
                            )
                        else:
                            print(f"  [{i}/{len(matches)}] OK {match_id} {home} vs {away}")
                    else:
                        print(f"  [{i}/{len(matches)}] OK {match_id} {home} vs {away} (no match data)")
                else:
                    summary["failed"] += 1
                    summary["errors"].append(match_id)
                    print(f"  [{i}/{len(matches)}] FAIL {match_id} {home} vs {away} (no stats)")
                    
            except Exception as exc:
                summary["failed"] += 1
                summary["errors"].append(match_id)
                print(f"  [{i}/{len(matches)}] ERROR {match_id} {home} vs {away}: {exc}")
            
            # Задержка между запросами (с рандомизацией)
            if i < len(matches):
                jitter = random.uniform(0.3, 0.7)
                time.sleep(delay + jitter)
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total:   {summary['total']}")
    print(f"  Skipped: {summary['skipped']} (already had stats)")
    print(f"  Fetched: {summary['fetched']}")
    print(f"  Saved:   {summary['saved']}")
    print(f"  Failed:  {summary['failed']}")
    if summary["errors"]:
        print(f"  Errors:  {', '.join(summary['errors'][:10])}")
    print(f"{'='*60}")
    
    return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch fetch match stats from Flashscore")
    parser.add_argument("--limit", type=int, default=0, help="Max matches to fetch (0=all)")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests (seconds)")
    parser.add_argument("--sport", type=int, default=1, help="Sport ID (1=football)")
    args = parser.parse_args()
    
    start = datetime.now()
    summary = batch_fetch_match_stats(
        limit=args.limit,
        offset=args.offset,
        delay=args.delay,
        sport=args.sport,
    )
    
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nTotal time: {elapsed:.1f}s")
    
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
