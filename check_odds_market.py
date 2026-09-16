"""Проверка market_name в таблице odds."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    # Проверяем уникальные market_name
    print("=== Уникальные market_name с OVER/UNDER ===")
    rows = conn.execute("""
        SELECT DISTINCT market_name FROM odds 
        WHERE market_name LIKE 'OVER%' OR market_name LIKE 'UNDER%'
        ORDER BY market_name
    """).fetchall()
    for r in rows:
        print(r[0])
    
    print("\n=== Сколько матчей имеют OVER/UNDER odds ===")
    count = conn.execute("""
        SELECT COUNT(DISTINCT match_id) FROM odds 
        WHERE market_name LIKE 'OVER%' OR market_name LIKE 'UNDER%'
    """).fetchone()[0]
    print(f"Матчей с тоталами: {count}")
    
    print("\n=== Примеры market_name ===")
    rows = conn.execute("SELECT DISTINCT market_name FROM odds LIMIT 30").fetchall()
    for r in rows:
        print(r[0])
