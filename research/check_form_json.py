import sqlite3
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

raw = conn.execute(
    "SELECT standings_json, form_json FROM match_snapshot WHERE match_id = '6mdpltmc'"
).fetchone()

for col in ("standings_json", "form_json"):
    val = raw[col]
    print(f"{col}: {'NULL' if val is None else str(len(val)) + ' симв'}")
    if val:
        d = json.loads(val)
        for k, v in d.items():
            print(f"   {k}: {len(v) if isinstance(v, list) else v} строк")

print()
print("--- сколько матчей с таблицей, но без формы:")
n = conn.execute(
    "SELECT COUNT(*) FROM match_snapshot "
    "WHERE standings_json IS NOT NULL AND form_json IS NULL"
).fetchone()[0]
print(n)

print()
print("--- примеры таких матчей:")
for r in conn.execute(
    "SELECT match_id FROM match_snapshot "
    "WHERE standings_json IS NOT NULL AND form_json IS NULL LIMIT 5"
):
    print("  ", r["match_id"])
