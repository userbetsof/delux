#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import json

DB_PATH = r"C:\papki\work\bets\delux\matches.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check specific match
cur.execute("""
    SELECT match_id, team_matches_json 
    FROM match_snapshot 
    WHERE match_id = 'EHD7TwkL'
""")
row = cur.fetchone()
if row:
    print(f"Match: {row['match_id']}")
    data = json.loads(row['team_matches_json'])
    print(f"\nTop-level keys: {list(data.keys())}")
    
    for team_key in data:
        print(f"\n  {team_key}: {list(data[team_key].keys())}")
        for side_key in data[team_key]:
            items = data[team_key][side_key]
            print(f"    {side_key}: {len(items)} matches")
            if items:
                print(f"      First: {items[0]}")
else:
    print("Match EHD7TwkL not found")

conn.close()
