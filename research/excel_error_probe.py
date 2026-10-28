import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

print("=== matches.prediction с ошибкой Excel")
for r in conn.execute(
    "SELECT prediction, COUNT(*) n FROM matches WHERE prediction LIKE '#%' GROUP BY prediction ORDER BY n DESC"
):
    print(f"  {r['prediction']!r}: {r['n']}")

print("=== strategy_predictions с ошибкой Excel")
for r in conn.execute(
    "SELECT strategy_id, prediction, COUNT(*) n FROM strategy_predictions "
    "WHERE prediction LIKE '#%' GROUP BY strategy_id, prediction ORDER BY n DESC"
):
    print(f"  #{r['strategy_id']} {r['prediction']!r}: {r['n']}")

print("=== Sniper с форой (проверка, что Ф1(0)/Ф1(-0.5) раньше недосчитывались")
for r in conn.execute(
    "SELECT prediction, COUNT(*) n FROM strategy_predictions WHERE strategy_id = 3 AND prediction LIKE 'Ф%' GROUP BY prediction"
):
    print(f"  {r['prediction']!r}: {r['n']}")
