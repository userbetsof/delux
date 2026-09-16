"""Проверка goal_probabilities для Q9s7530B."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    row = conn.execute("SELECT * FROM goal_probabilities WHERE match_id = ?", ("Q9s7530B",)).fetchone()
    if row:
        print("goal_probabilities для Q9s7530B (футбол, лимит 6):")
        
        # home_goals_0..5
        home_0_5 = row[2:8]
        # home_goals_6..12
        home_6_12 = row[14:21]
        
        print(f"\n  HOME:")
        for i in range(6):
            print(f"    P({i}) = {home_0_5[i]:.2f}%")
        print(f"    P(6+) = {home_6_12[0]:.2f}% (колонка 6)")
        print(f"    P(7+) = {home_6_12[1]:.2f}% (колонка 7)")
        print(f"    ...")
        print(f"    P(12+) = {home_6_12[6]:.2f}% (колонка 12)")
        
        # Сумма
        home_total = sum(home_0_5) + sum(home_6_12)
        print(f"\n  Сумма HOME: {home_total:.2f}%")
    else:
        print("Нет goal_probabilities для Q9s7530B")
