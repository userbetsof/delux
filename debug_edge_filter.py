#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import json

DB_PATH = r"C:\papki\work\bets\delux\matches.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Тестируем JSON extraction
print("=== Тест JSON extraction ===")
cur.execute("""
    SELECT id, notes,
           json_extract(notes, '$.difference') as diff_json,
           json_extract(notes, '$.edge') as edge_json,
           CAST(COALESCE(json_extract(notes, '$.difference'), json_extract(notes, '$.edge')) AS REAL) as edge_raw
    FROM strategy_predictions
    WHERE match_id = '0dnoNM9b' AND strategy_id = 8
    LIMIT 1
""")
row = cur.fetchone()
if row:
    print(f"id={row[0]}")
    print(f"notes (first 200): {str(row[1])[:200]}")
    print(f"diff_json={row[2]}")
    print(f"edge_json={row[3]}")
    print(f"edge_raw={row[4]}")

# Тестируем полный SQL запрос с обоими фильтрами
print("\n=== Полный SQL с date + edge ===")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM strategy_predictions sp
    LEFT JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date >= '2026.09.15 00:00'
      AND m.match_date <= '2026.09.19 23:59'
      AND CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL) IS NOT NULL
""")
print(f"Прогнозы с edge за 15-19 сентября: {cur.fetchone()[0]}")

# Проверяем edge значения
print("\n=== Edge значения за 15-19 сентября ===")
cur.execute("""
    SELECT sp.id, sp.match_id, sp.prediction, sp.odds,
           CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL) as edge_raw,
           CASE WHEN ABS(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge'))) <= 1.5
                THEN CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL) * 100.0
                ELSE CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL)
           END as edge_pp
    FROM strategy_predictions sp
    LEFT JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date >= '2026.09.15 00:00'
      AND m.match_date <= '2026.09.19 23:59'
    LIMIT 10
""")
print("id | match_id | prediction | odds | edge_raw | edge_pp")
for row in cur.fetchall():
    print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}")

# Проверяем фильтры по edge
print("\n=== Фильтр edge >= 5 ===")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM strategy_predictions sp
    LEFT JOIN matches m ON m.match_id = sp.match_id
    WHERE m.match_date >= '2026.09.15 00:00'
      AND m.match_date <= '2026.09.19 23:59'
      AND CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL) IS NOT NULL
      AND (CASE WHEN ABS(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge'))) <= 1.5
                THEN CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL) * 100.0
                ELSE CAST(COALESCE(json_extract(sp.notes, '$.difference'), json_extract(sp.notes, '$.edge')) AS REAL)
           END) >= 5
""")
print(f"Прогнозы с edge >= 5: {cur.fetchone()[0]}")

conn.close()
