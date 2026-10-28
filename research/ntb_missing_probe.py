import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """
    SELECT m.match_id, m.prediction, m.match_status,
           (SELECT prediction FROM strategy_predictions sp
             WHERE sp.match_id = m.match_id AND sp.strategy_id = 1) AS ntb,
           (SELECT prediction FROM strategy_predictions sp
             WHERE sp.match_id = m.match_id AND sp.strategy_id = 3) AS sniper
    FROM matches m
    WHERE m.prediction IS NOT NULL AND TRIM(m.prediction) NOT IN ('', '-')
    """
).fetchall()

no_ntb = [r for r in rows if not r["ntb"] or not str(r["ntb"]).strip()]
print(f"матчей с главным прогнозом: {len(rows)}")
print(f"из них без строки NTB (#1): {len(no_ntb)}")
for r in no_ntb[:20]:
    print(f"  {r['match_id']} status={r['match_status']} main={r['prediction']!r} sniper={r['sniper']!r}")

fut = [r for r in no_ntb if r["match_status"] in (0, 1, 2, None)]
print(f"из них ещё не завершены (status 0/1/2): {len(fut)}")
