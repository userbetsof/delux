"""Показать форму хозяев и гостей из снимка — в том порядке, что видит движок."""

import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

MID = "ncRVhYJ7"

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

m = conn.execute(
    "SELECT m.match_id, ht.name AS home, at.name AS away FROM matches m "
    "JOIN teams ht ON ht.id = m.home_team_id "
    "JOIN teams at ON at.id = m.away_team_id WHERE m.match_id = ?",
    (MID,),
).fetchone()
print(f"матч: {m['home']} (хозяева) - {m['away']} (гости)")
print()

row = conn.execute(
    "SELECT form_json, fetched_at FROM match_snapshot WHERE match_id = ?", (MID,)
).fetchone()
form = json.loads(row["form_json"])
print(f"снимок от {row['fetched_at']}")
print(f"секции: {list(form.keys())}")

for section in ("home", "away", "overall"):
    items = form.get(section) or []
    if not items:
        print(f"\n[{section}]: пусто")
        continue
    print(f"\n[{section}] — {len(items)} строк:")
    # показываем только команды из матча
    for it in items:
        team = str(it.get("team") or "")
        if team in (m["home"], m["away"]):
            print(
                f"  {team:22} И={it.get('played')} В={it.get('wins')} "
                f"Н={it.get('draws')} П={it.get('losses')} "
                f"ЗМ={it.get('scored')} ПМ={it.get('conceded')} О={it.get('points')}"
            )
