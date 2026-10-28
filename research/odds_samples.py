import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

queries = {
    "тотал (ТБ)": "SELECT prediction, odds FROM strategy_predictions WHERE strategy_id = 3 AND prediction LIKE 'ТБ%' AND odds IS NOT NULL LIMIT 5",
    "исход (П1/П2)": "SELECT prediction, odds FROM strategy_predictions WHERE strategy_id IN (1,2) AND prediction IN ('П1','П2') AND odds IS NOT NULL LIMIT 5",
    "двойной шанс (1X)": "SELECT prediction, odds FROM strategy_predictions WHERE prediction = '1X' AND odds IS NOT NULL LIMIT 5",
    "фора (Ф1(0))": "SELECT prediction, odds FROM strategy_predictions WHERE prediction LIKE 'Ф%' AND odds IS NOT NULL LIMIT 5",
    "ОЗ": "SELECT prediction, odds FROM strategy_predictions WHERE prediction LIKE '%ОЗ%' AND odds IS NOT NULL LIMIT 5",
}
for title, sql in queries.items():
    print("===", title)
    for r in conn.execute(sql):
        print(f"  {r['prediction']!r} @ {r['odds']}")
