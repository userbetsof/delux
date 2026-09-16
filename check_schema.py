"""Проверка схемы goal_probabilities."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, GOAL_PROB_COLUMNS

with get_db_connection() as conn:
    cols = conn.execute("PRAGMA table_info(goal_probabilities)").fetchall()
    print("=== Columns in goal_probabilities ===")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")
    print(f"\nTotal columns: {len(cols)}")
    print(f"GOAL_PROB_COLUMNS count: {len(GOAL_PROB_COLUMNS)}")
