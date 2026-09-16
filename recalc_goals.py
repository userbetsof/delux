"""Пересчёт goal_probabilities для матчей с нулевыми значениями."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, GOAL_PROB_BINS, GOAL_PROB_COLUMNS

def recalc_goals():
    with get_db_connection() as conn:
        # Находим матчи с нулевыми goal_probabilities
        rows = conn.execute(f"""
            SELECT match_id FROM goal_probabilities
            WHERE home_goals_1 = 0 AND home_goals_2 = 0
            AND away_goals_1 = 0 AND away_goals_2 = 0
            AND home_goals_0 = 100 AND away_goals_0 = 100
        """).fetchall()
        
        print(f"Найдено {len(rows)} матчей с нулевыми вероятностями")
        
        for row in rows:
            match_id = row[0]
            # Удаляем плохие данные
            conn.execute("DELETE FROM goal_probabilities WHERE match_id = ?", (match_id,))
            print(f"  Удалены нулевые данные для {match_id}")
        
        conn.commit()
        print("Готово. Теперь нужно перезапустить анализ для этих матчей через match_analysis.py")

if __name__ == "__main__":
    recalc_goals()
