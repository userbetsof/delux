#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3

DB_PATH = r"C:\papki\work\bets\delux\matches.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Проверяем прогнозы за 15-19 сентября 2026
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM strategy_predictions sp
    JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date >= '2026.09.15'
      AND m.match_date <= '2026.09.19'
""")
count = cur.fetchone()['cnt']
print(f"Прогнозы за 15-19 сентября 2026: {count}")

# Проверяем формат дат в БД
cur.execute("""
    SELECT match_date FROM matches 
    WHERE match_date LIKE '2026.09.1%'
    ORDER BY match_date
    LIMIT 5
""")
dates = cur.fetchall()
print(f"\nПримеры дат:")
for d in dates:
    print(f"  - {d['match_date']}")

# Проверяем все даты сентября
cur.execute("""
    SELECT DISTINCT substr(match_date, 1, 10) as day
    FROM matches
    WHERE match_date LIKE '2026.09%'
    ORDER BY day
""")
days = cur.fetchall()
print(f"\nДаты в сентябре 2026:")
for d in days:
    print(f"  - {d['day']}")

# Проверяем прогнозы за все 15 сентября
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM strategy_predictions sp
    JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date LIKE '2026.09.15%'
""")
count_15 = cur.fetchone()['cnt']
print(f"\nПрогнозы 15 сентября: {count_15}")

# Проверяем прогнозы за 19 сентября
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM strategy_predictions sp
    JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date LIKE '2026.09.19%'
""")
count_19 = cur.fetchone()['cnt']
print(f"Прогнозы 19 сентября: {count_19}")

conn.close()
