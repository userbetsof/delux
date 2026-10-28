import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from odds_normalize import market_key, prediction_market
from prediction_odds import odds_lookup, resolve_prediction_odds

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

for mid in ("YZpF3sVN", "l0jpbLho", "xtmHKGT0"):
    print("===", mid)
    rows = conn.execute(
        "SELECT market_name, odds_value FROM odds WHERE match_id = ? AND market_name LIKE 'HANDICAP%'",
        (mid,),
    ).fetchall()
    print("  handicap rows:", [(r["market_name"], r["odds_value"]) for r in rows])
    pred = conn.execute(
        "SELECT prediction, odds FROM strategy_predictions WHERE match_id = ? AND strategy_id = 9",
        (mid,),
    ).fetchone()
    if pred:
        print("  pred:", pred["prediction"], "odds:", pred["odds"])
        print("  market:", prediction_market(pred["prediction"]))
        lookup = odds_lookup(
            conn.execute("SELECT market_name, odds_value FROM odds WHERE match_id = ?", (mid,)).fetchall()
        )
        print("  resolved:", resolve_prediction_odds(pred["prediction"], lookup))
