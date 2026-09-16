"""Найти матчи без коэффициентов."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    # Матчи без odds
    rows = conn.execute("""
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id
        FROM matches m
        LEFT JOIN odds o ON m.match_id = o.match_id
        WHERE o.match_id IS NULL
        ORDER BY m.match_date
    """).fetchall()
    
    print(f"Матчей без коэффициентов: {len(rows)}")
    for r in rows[:20]:
        print(f"  {r[0]} | {r[1]} | home={r[2]} | away={r[3]}")
