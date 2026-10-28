import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from db import get_database_path
from prediction_odds import odds_lookup, resolve_prediction_odds

conn = sqlite3.connect(get_database_path())
conn.row_factory = sqlite3.Row

missing = {}
resolved = {}
for mid in [r[0] for r in conn.execute("SELECT DISTINCT match_id FROM strategy_predictions")]:
    rows = conn.execute(
        "SELECT market_name, odds_value FROM odds WHERE match_id = ?", (mid,)
    ).fetchall()
    if not rows:
        continue
    lookup = odds_lookup(rows)
    for r in conn.execute(
        "SELECT strategy_id, prediction FROM strategy_predictions "
        "WHERE match_id = ? AND (odds IS NULL OR odds = '' OR odds <= 1)",
        (mid,),
    ):
        v = resolve_prediction_odds(r["prediction"], lookup)
        bucket = resolved if v is not None else missing
        key = (r["strategy_id"], r["prediction"])
        bucket[key] = bucket.get(key, 0) + 1

print("=== НЕ РАЗРЕШЕНО (нет такого рынка в odds)")
for (sid, pred), n in sorted(missing.items(), key=lambda kv: -kv[1])[:40]:
    print(f"  #{sid} {pred!r}: {n}")
print("итого не разрешено:", sum(missing.values()))
print("итого разрешено:", sum(resolved.values()))

print("\n=== нет odds вообще")
cnt = conn.execute(
    "SELECT COUNT(*) FROM strategy_predictions sp WHERE (sp.odds IS NULL OR sp.odds = '' OR sp.odds <= 1) "
    "AND NOT EXISTS (SELECT 1 FROM odds o WHERE o.match_id = sp.match_id)"
).fetchone()[0]
print("строк без кф и без odds у матча:", cnt)
