"""Загрузка коэффициентов для матчей без odds из Flashscore API."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, insert_or_get_team, insert_or_get_league, insert_or_get_country, parse_league
from odds_service import load_odds, canonicalize_market, split_canonical
from odds_normalize import to_float as odds_to_float
from date_utils import normalize_match_date


def load_odds_for_matches():
    with get_db_connection() as conn:
        # Матчи без коэффициентов
        matches = conn.execute("""
            SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id, m.league_id, m.sport
            FROM matches m
            LEFT JOIN odds o ON m.match_id = o.match_id
            WHERE o.match_id IS NULL AND m.match_id != ''
            ORDER BY m.match_date
        """).fetchall()
        
        print(f"Матчей без коэффициентов: {len(matches)}")
        
        loaded = 0
        failed = 0
        
        for match_id, match_date, home_id, away_id, league_id, sport in matches:
            try:
                # Загружаем odds из API
                code, odds_data = load_odds(match_id, None)
                
                if code != 0:
                    print(f"  SKIP {match_id}: код {code}")
                    failed += 1
                    continue
                
                if not odds_data or not odds_data.bookmakers:
                    print(f"  SKIP {match_id}: нет bookmakers")
                    failed += 1
                    continue
                
                # Сохраняем odds в БД
                cursor = conn.cursor()
                cursor.execute("DELETE FROM odds WHERE match_id = ?", (match_id,))
                
                batch = []
                for m in odds_data.all_markets_flat():
                    canon = canonicalize_market(
                        m.get("market_name"),
                        outcome=m.get("outcome"),
                        side=m.get("side"),
                        line_value=m.get("line_value"),
                    )
                    if not canon:
                        continue
                    meta = split_canonical(canon)
                    batch.append((
                        match_id,
                        canon,
                        meta.get("outcome") or m.get("outcome"),
                        meta.get("side") or m.get("side"),
                        meta.get("line_value") if meta.get("line_value") is not None else m.get("line_value"),
                        m["odds_value"],
                    ))
                
                if batch:
                    cursor.executemany(
                        """
                        INSERT INTO odds (match_id, market_name, outcome, side, line_value, odds_value)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    loaded += 1
                    if loaded <= 5:
                        print(f"  {match_id}: {len(batch)} market rows")
                else:
                    failed += 1
                    print(f"  SKIP {match_id}: нет market rows")
                
                conn.commit()
                
            except Exception as e:
                print(f"  ERROR {match_id}: {e}")
                failed += 1
                conn.rollback()
        
        print(f"\nИтого: загружено {loaded}, ошибок {failed}")
        
        # Проверка
        remaining = conn.execute("""
            SELECT COUNT(*) FROM matches m
            LEFT JOIN odds o ON m.match_id = o.match_id
            WHERE o.match_id IS NULL AND m.match_id != ''
        """).fetchone()[0]
        print(f"Осталось без odds: {remaining}")


if __name__ == "__main__":
    load_odds_for_matches()
