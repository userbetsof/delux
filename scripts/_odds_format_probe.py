import sqlite3
conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row
print("1X2 rows sample:")
for r in conn.execute("SELECT match_id, market_name, outcome, side, line_value, odds_value, home_win_odds FROM odds WHERE UPPER(market_name) LIKE '%1X2%' LIMIT 12"):
    print(dict(r))
print("HANDICAP sample:")
for r in conn.execute("SELECT match_id, market_name, outcome, side, line_value, odds_value FROM odds WHERE market_name='HANDICAP' LIMIT 5"):
    print(dict(r))
print("OVER sample:")
for r in conn.execute("SELECT match_id, market_name, outcome, side, line_value, odds_value FROM odds WHERE market_name='OVER' LIMIT 5"):
    print(dict(r))
print("distinct outcomes for 1X2:", list(conn.execute("SELECT outcome, COUNT(*) c FROM odds WHERE market_name='1X2' GROUP BY outcome")))
