"""Проверка Q9s7530B."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    # Проверяем есть ли goal_probabilities
    gp = conn.execute("SELECT COUNT(*) FROM goal_probabilities WHERE match_id = ?", ("Q9s7530B",)).fetchone()
    print(f"goal_probabilities для Q9s7530B: {gp[0]}")
    
    # Проверяем OVER/UNDER odds
    odds = conn.execute("""
        SELECT market_name, odds_value FROM odds 
        WHERE match_id = 'Q9s7530B' AND (market_name LIKE 'OVER%' OR market_name LIKE 'UNDER%')
        ORDER BY market_name
    """).fetchall()
    
    print(f"\nOVER/UNDER odds для Q9s7530B ({len(odds)} строк):")
    for o in odds[:20]:
        print(f"  {o[0]}: {o[1]}")
