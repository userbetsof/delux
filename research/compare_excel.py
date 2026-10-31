import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Ожидаемые значения из Excel (хозяева, ничья, гости)
EXPECTED = {
    "1 пр": (73, 14, 84),
    "2 пр": (3, 28, 69),
    "de lux": (3, 21, 75),
    "poisson": (10, 13, 77),
    "ср взвеш": (4, 9, 88),
    "mill": (40, -49, 109),
    "Mini Vini": (2, 29, 69),
    "Elizabet": (8, 17, 75),
    "5Match p": (39, 20, 41),
    "5Match": (51, 8, 41),
}

MID = "ncRVhYJ7"

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

m = conn.execute(
    "SELECT match_id, match_date, prediction, match_status, score_home, score_away "
    "FROM matches WHERE match_id = ?",
    (MID,),
).fetchone()
print("матч:", dict(m) if m else "НЕ НАЙДЕН")
print()

rows = conn.execute(
    "SELECT o.strategy_id AS sid, s.strategy_name AS name, "
    "       o.home_win_prob AS h, o.draw_prob AS d, o.away_win_prob AS a "
    "FROM outcome_probabilities o "
    "LEFT JOIN sub_strategies s ON s.id = o.strategy_id "
    "WHERE o.match_id = ? ORDER BY o.strategy_id",
    (MID,),
).fetchall()

print("стратегия    |  БД: хозяева/ничья/гости | Excel            | статус")
print("-" * 78)
for r in rows:
    name = r["name"] or f"#{r['sid']}"
    h = round(r["h"] or 0, 1)
    d = round(r["d"] or 0, 1)
    a = round(r["a"] or 0, 1)
    exp = EXPECTED.get(name)
    if exp:
        eh, ed, ea = exp
        # сравнение с допуском 1.5 (округление в Excel)
        close = all(abs(x - y) <= 1.5 for x, y in ((h, eh), (d, ed), (a, ea)))
        status = "OK" if close else "РАСХОЖДЕНИЕ"
        exp_txt = f"{eh:5.0f} {ed:5.0f} {ea:5.0f}"
    else:
        status = "—"
        exp_txt = "                 "
    print(f"{name:12} | {h:7.1f} {d:7.1f} {a:7.1f} | {exp_txt}  | {status}")

print()
print(f"строк в БД: {len(rows)}")
