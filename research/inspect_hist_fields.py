import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row
MID = "KdLPRx82"

row = conn.execute(
    "SELECT h2h_json, team_matches_json FROM match_snapshot WHERE match_id = ?",
    (MID,),
).fetchone()

print("=== h2h_json: первый элемент ===")
d = json.loads(row["h2h_json"])
print(json.dumps(d["all"][0], ensure_ascii=False, indent=2) if d.get("all") else "пусто")

print()
print("=== team_matches home.all: первый элемент ===")
tm = json.loads(row["team_matches_json"])
home = (tm.get("home") or {}).get("all") or []
print(json.dumps(home[0], ensure_ascii=False, indent=2) if home else "пусто")

print()
print("=== сколько записей с непустым venue ===")
for name, items in (
    ("h2h", d.get("all") or []),
    ("home_all", home),
    ("away_all", (tm.get("away") or {}).get("all") or []),
):
    with_venue = sum(1 for x in items if str(x.get("venue") or "").strip())
    with_ht = sum(1 for x in items if x.get("home_ht") not in (None, "", 0))
    print(f"  {name}: всего {len(items)}, с venue {with_venue}, с home_ht≠0 {with_ht}")
