"""Расчёт goal_probabilities из коэффициентов OVER/UNDER с учётом вида спорта."""
import sys
import os
import math
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, odds_to_float

# Лимиты тоталов по виду спорта (максимальное количество голов для расчёта)
GOAL_LIMITS = {
    1: 6,   # футбол: 0-6
    4: 9,   # хоккей: 0-9
    6: 10,  # бейсбол: 0-10
}


def fit_poisson(lam, max_goals):
    """Распределение Пуассон с обрезкой на max_goals."""
    probs = []
    for k in range(max_goals):  # k=0..max_goals-1
        probs.append(math.exp(-lam) * lam**k / math.factorial(k))
    probs.append(1.0 - sum(probs))  # probs[max_goals] = P(max_goals+)
    return probs


def _poisson_cdf(lam, k_max):
    total = 0.0
    for k in range(int(k_max) + 2):
        total += math.exp(-lam) * lam**k / math.factorial(k)
    return total


def _solve_cdf(cdf_func, target, low, high):
    for _ in range(100):
        mid = (low + high) / 2
        val = cdf_func(mid)
        if abs(val - target) < 0.0001:
            return mid
        if val > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def recalc_goals_from_odds():
    with get_db_connection() as conn:
        # П��лучаем реальный порядок колонок из таблицы
        cols_info = conn.execute("PRAGMA table_info(goal_probabilities)").fetchall()
        goal_cols = [c[1] for c in cols_info if c[1].startswith('home_goals_') or c[1].startswith('away_goals_')]
        print(f"Колонки в таблице ({len(goal_cols)}): {goal_cols}")
        
        # Получаем все матчи с их sport
        matches = conn.execute("""
            SELECT m.match_id, m.sport FROM matches m
        """).fetchall()
        
        print(f"Всего матчей: {len(matches)}")
        
        count = 0
        errors = 0
        skipped = 0
        
        for match_id, sport in matches:
            if not match_id:
                continue
            
            # Определяем лимит тоталов для этого вида спорта
            goal_limit = GOAL_LIMITS.get(sport, 6)
            GOAL_PROB_BINS = goal_limit + 1  # 0..goal_limit
            
            try:
                odds_rows = conn.execute(
                    "SELECT market_name, odds_value FROM odds WHERE match_id = ?",
                    (match_id,)
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
                
                lambdas = []
                for line_val, over_odds in over_lines.items():
                    under_odds = under_lines.get(line_val)
                    if not under_odds:
                        continue
                    
                    p_under = 1.0 - 1.0 / under_odds
                    if not (0.001 < p_under < 0.999):
                        continue
                    
                    if line_val <= 0.5:
                        lam = -math.log(p_under)
                    elif line_val <= 1.5:
                        lam = _solve_cdf(
                            lambda l: math.exp(-l) * (1 + l),
                            p_under, 0.1, 10
                        )
                    else:
                        lam = _solve_cdf(
                            lambda l: _poisson_cdf(l, line_val),
                            p_under, 0.1, 10
                        )
                    
                    if lam and 0 < lam <= 10:
                        lambdas.append(lam)
                
                if not lambdas:
                    skipped += 1
                    continue
                
                avg_lambda = sum(lambdas) / len(lambdas)
                
                # Рассчитываем распределение Пуассон с учётом лимита спорта
                home_probs = fit_poisson(avg_lambda, goal_limit)
                away_probs = fit_poisson(avg_lambda, goal_limit)
                
                # Формируем значения в порядке колонок таблицы
                # goal_cols: home_0-5, away_0-5, home_6-12, away_6-12
                # home_probs имеет длину goal_limit+2 (0..goal_limit, goal_limit+)
                # home_probs[-1] = P(goal_limit+)
                values = []
                for col in goal_cols:
                    idx = int(col.split('_')[-1])
                    if col.startswith('home_goals_'):
                        if idx <= 5:  # home_0-5
                            values.append(home_probs[idx])
                        else:  # home_6-12 -> все = P(6+)
                            values.append(home_probs[-1])
                    else:  # away_goals_
                        if idx <= 5:  # away_0-5
                            values.append(away_probs[idx])
                        else:  # away_6-12 -> все = P(6+)
                            values.append(away_probs[-1])
                
                # Конвертируем в проценты
                values = [float(v) * 100 for v in values]
                
                # Строим INSERT динамически
                placeholders = ", ".join(["?"] * (1 + len(goal_cols)))
                col_list = ", ".join(["match_id"] + goal_cols)
                sql = f"INSERT OR REPLACE INTO goal_probabilities ({col_list}) VALUES ({placeholders})"
                
                conn.execute(sql, (match_id, *values))
                
                count += 1
                if count <= 15:
                    sport_name = {1: "футбол", 4: "хоккей", 6: "бейсбол"}.get(sport, str(sport))
                    print(f"  {match_id}: {sport_name}, lambda={avg_lambda:.3f}, P(0)={home_probs[0]*100:.1f}%, P({goal_limit}+)={home_probs[-1]*100:.1f}%")
                
            except Exception as e:
                print(f"  ERROR {match_id}: {e}")
                import traceback
                traceback.print_exc()
                errors += 1
        
        conn.commit()
        print(f"\nИтого: рассчитано {count}, ошибок {errors}, пропущено {skipped}")
        
        remaining = conn.execute("""
            SELECT COUNT(*) FROM matches m
            LEFT JOIN goal_probabilities g ON m.match_id = g.match_id
            WHERE g.match_id IS NULL
        """).fetchone()[0]
        print(f"Осталось без goal_probabilities: {remaining}")


if __name__ == "__main__":
    recalc_goals_from_odds()
