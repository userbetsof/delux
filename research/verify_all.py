"""Сверка Excel (значения от пользователя) с базой DeluX.

Excel-скриншот содержит 3 числа перед названием стратегии:
    хозяева, ничья, гости
"""

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

MID = "ncRVhYJ7"

# из скриншота: strategy_name -> (хозяева, ничья, гости)
EXCEL = {
    "1 пр": (3, 14, 84),
    "2 пр": (3, 28, 69),
    "de lux": (3, 21, 75),
    "poisson": (10, 13, 77),
    "ср взвеш": (4, 9, 88),
    "mill": (40, -49, 109),
    "Mini Vini": (2, 29, 69),
    "Elizabet": (8, 17, 75),
    "5Match p": (39, 20, 41),
    "5Match": (51, 8, 41),
}

# что показывает Excel на самом деле (из ячеек листа Incognito DATA и др.)
# для 1 пр проверили: J13/K13/L13 = 2% / 29% / 69%
ACTUAL_EXCEL = {
    "1 пр": (2, 29, 69),
}

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT o.strategy_id AS sid, s.strategy_name AS name, "
    "       o.home_win_prob AS h, o.draw_prob AS d, o.away_win_prob AS a "
    "FROM outcome_probabilities o "
    "LEFT JOIN sub_strategies s ON s.id = o.strategy_id "
    "WHERE o.match_id = ? ORDER BY o.strategy_id",
    (MID,),
).fetchall()

print("стратегия  |      БД (х/н/г)      |     Excel (х/н/г)     |  Σ БД |  Σ Excel | ито")
print("-" * 84)
for r in rows:
    name = r["name"] or f"#{r['sid']}"
    h, d, a = round(r["h"] or 0), round(r["d"] or 0), round(r["a"] or 0)
    sc = ACTUAL_EXCEL.get(name) or EXCEL.get(name)
    if not sc:
        continue
    eh, ed, ea = sc
    sum_db = h + d + a
    sum_ex = eh + ed + ea
    ok = all(abs(x - y) <= 3 for x, y in ((h, eh), (d, ed), (a, ea)))
    print(
        f"{name:10} | {h:6} {d:6} {a:6} | {eh:6} {ed:6} {ea:6} | {sum_db:5} | {sum_ex:8} | "
        f"{'OK' if ok else 'РАСХОД'}"
    )

print()
print("Если сумма Excel ≠ 100 — данные в Excel неполные (не загружен матч)")
