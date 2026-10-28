import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

print("--- KdLPRx82")
for r in conn.execute("SELECT match_id, strategy_id, prediction, odds FROM strategy_predictions WHERE match_id = 'KdLPRx82'"):
    print(dict(r))

print("--- matches.prediction")
for r in conn.execute("SELECT match_id, prediction FROM matches WHERE match_id = 'KdLPRx82'"):
    print(dict(r))

print("--- CS рынки в odds")
for r in conn.execute("SELECT market_name, COUNT(*) n FROM odds WHERE market_name LIKE 'CS %' GROUP BY market_name ORDER BY n DESC LIMIT 10"):
    print(dict(r))
print("CS total:", conn.execute("SELECT COUNT(*) FROM odds WHERE market_name LIKE 'CS %'").fetchone()[0])

print("--- whoscored rows without odds")
for r in conn.execute("SELECT match_id, prediction, odds, notes FROM strategy_predictions WHERE strategy_id = 9 AND (odds IS NULL OR odds = '')"):
    print(dict(r))
