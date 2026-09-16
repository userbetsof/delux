"""Проверка расчёта lambda для Q9s7530B."""
import math

# Коэффициенты из БД для Q9s7530B
over_under = {
    0.5: (1.02, 8.0),
    0.75: (1.03, 7.45),
    1.0: (1.05, 6.65),
    1.25: (1.18, 3.96),
    1.5: (1.31, 2.98),
    1.75: (1.41, 2.63),
    2.0: (1.53, 2.26),
    2.25: (1.89, 1.99),
    2.5: (2.16, 1.77),
    2.75: (2.34, 1.5),
    3.0: (2.92, 1.33),
    3.25: (3.24, 1.26),
    3.5: (3.56, 1.22),
    3.75: (4.47, 1.13),
    4.0: (6.35, 1.05),
    4.5: (7.1, 1.03),
}

def poisson_cdf(lam, k_max):
    total = 0.0
    for k in range(int(k_max) + 2):
        total += math.exp(-lam) * lam**k / math.factorial(k)
    return total

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

lambdas = []
for line_val, (over_odds, under_odds) in over_under.items():
    p_under = 1.0 - 1.0 / under_odds
    if not (0.001 < p_under < 0.999):
        continue
    
    if line_val <= 0.5:
        lam = -math.log(p_under)
    elif line_val <= 1.5:
        lam = solve_cdf(lambda l: math.exp(-l) * (1 + l), p_under, 0.1, 10)
    else:
        lam = solve_cdf(lambda l: poisson_cdf(l, line_val), p_under, 0.1, 10)
    
    if lam and 0 < lam < 10:
        lambdas.append(lam)
        print(f"line={line_val}: over={over_odds}, under={under_odds}, p_under={p_under:.4f}, lambda={lam:.4f}")

avg_lambda = sum(lambdas) / len(lambdas)
print(f"\nСредний lambda: {avg_lambda:.4f}")
print(f"Количество lambdas: {len(lambdas)}")

# Рассчитаем распределение
def fit_poisson(lam, max_goals):
    probs = []
    for k in range(max_goals):
        probs.append(math.exp(-lam) * lam**k / math.factorial(k))
    probs.append(1.0 - sum(probs))
    return probs

probs = fit_poisson(avg_lambda, 6)
print(f"\nРаспределение для lambda={avg_lambda:.4f}:")
total = 0
for i, p in enumerate(probs):
    print(f"  P({i}) = {p*100:.2f}%")
    total += p
print(f"  Сумма: {total*100:.2f}%")
