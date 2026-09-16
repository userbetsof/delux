"""Проверка видов спорта в базе."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    rows = conn.execute("""
        SELECT sport, COUNT(*) as cnt
        FROM matches
        GROUP BY sport
        ORDER BY sport
    """).fetchall()
    
    print("Виды спорта:")
    for r in rows:
        print(f"  sport={r[0]}: {r[1]} матчей")
