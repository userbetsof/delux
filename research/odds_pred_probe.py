import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
c.row_factory = sqlite3.Row

print("--- odds coverage per strategy")
for r in c.execute(
    "SELECT strategy_id, COUNT(*) n, "
    "SUM(CASE WHEN odds IS NOT NULL AND odds <> '' THEN 1 ELSE 0 END) w "
    "FROM strategy_predictions GROUP BY strategy_id"
):
    print(r["strategy_id"], "rows", r["n"], "with_odds", r["w"])

print("--- distinct predictions for calc/favorites/stavka strategies")
for r in c.execute(
    "SELECT DISTINCT prediction FROM strategy_predictions "
    "WHERE strategy_id IN (1,2,3,4,5,6,10) ORDER BY prediction"
):
    print(repr(r["prediction"]))

print("--- KdLPRx82 strategy_predictions")
for r in c.execute("SELECT * FROM strategy_predictions WHERE match_id = 'KdLPRx82'"):
    print(dict(r))

print("--- KdLPRx82 odds")
for r in c.execute(
    "SELECT market_name, outcome, side, line_value, odds_value FROM odds WHERE match_id = 'KdLPRx82'"
):
    print(dict(r))

print("--- distinct canonical markets in odds table (top 60)")
for r in c.execute(
    "SELECT market_name, COUNT(*) n FROM odds GROUP BY market_name ORDER BY n DESC LIMIT 60"
):
    print(repr(r["market_name"]), r["n"])
