"""Проверка OVER/UNDER odds для Q9s7530B."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, odds_to_float

with get_db_connection() as conn:
    odds_rows = conn.execute(
        "SELECT market_name, odds_value FROM odds WHERE match_id = 'Q9s7530B'"
    ).fetchall()
    
    over_lines = {}
    under_lines = {}
    
    for market_name, odds_val in odds_rows:
        if not market_name or not odds_val:
            continue
        mv = market_name.strip()
        ov = odds_to_float(odds_val)
        if not ov or ov <= 1:
            continue
        
        if mv.startswith("OVER "):
            try:
                line = float(mv[5:])
                over_lines[line] = ov
            except ValueError:
                pass
        elif mv.startswith("UNDER "):
            try:
                line = float(mv[6:])
                under_lines[line] = ov
            except ValueError:
                pass
    
    print(f"OVER lines: {over_lines}")
    print(f"UNDER lines: {under_lines}")
    
    # Проверим что есть общие линии
    common = set(over_lines.keys()) & set(under_lines.keys())
    print(f"Общие линии: {common}")
    
    if not common:
        print("Нет общих линий OVER/UNDER!")
