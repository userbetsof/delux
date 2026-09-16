"""Проверка порядка колонок."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    cols_info = conn.execute("PRAGMA table_info(goal_probabilities)").fetchall()
    goal_cols = [c[1] for c in cols_info if c[1].startswith('home_goals_') or c[1].startswith('away_goals_')]
    
    print(f"goal_cols ({len(goal_cols)}):")
    for i, col in enumerate(goal_cols):
        print(f"  [{i}] {col}")
