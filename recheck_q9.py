"""Пересчёт и проверка Q9s7530B."""
import sys
import os
import math
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection, odds_to_float

def fit_poisson(lam, max_goals):
    probs = []
    for k in range(max_goals):
        probs.append(math.exp(-lam) * lam**k / math.factorial(k))
    probs.append(1.0 - sum(probs))
    return probs

def solve_cdf(cdf_func, target, low, high):
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

match_id = "Q9s7530B"
sport = 1  # футбол
goal_limit = 6

with get_db_connection() as conn:
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
            lam = solve_cdf(lambda l: math.exp(-l) * (1 + l), p_under, 0.1, 10)
        else:
            lam = 3.5  # fallback
        
        if lam and 0 < lam < 10:
            lambdas.append(lam)
    
    if lambdas:
        avg_lambda = sum(lambdas) / len(lambdas)
        print(f"lambda = {avg_lambda:.4f}")
        
        probs = fit_poisson(avg_lambda, goal_limit)
        print(f"\nРаспределение:")
        total = 0
        for i, p in enumerate(probs):
            print(f"  P({i}) = {p*100:.2f}%")
            total += p
        print(f"  Сумма: {total*100:.2f}%")
    else:
        print("Не удалось рассчитать lambda")
