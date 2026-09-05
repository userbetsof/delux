import sqlite3
conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
print("status", list(conn.execute("SELECT match_status, COUNT(*) FROM matches GROUP BY match_status")))
print("pending", conn.execute("SELECT COUNT(*) FROM matches WHERE match_status='Не начался'").fetchone()[0])
print("odds sample markets", list(conn.execute("SELECT market_name, COUNT(*) c FROM odds GROUP BY market_name ORDER BY c DESC LIMIT 20")))
print("matches with 1x2 wide", conn.execute("SELECT COUNT(DISTINCT match_id) FROM odds WHERE home_win_odds IS NOT NULL").fetchone()[0])
print("matches with 1X2_1 market", conn.execute("SELECT COUNT(DISTINCT match_id) FROM odds WHERE UPPER(market_name)='1X2_1'").fetchone()[0])
