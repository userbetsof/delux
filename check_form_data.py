"""Check form data availability for today's matches."""
import sys
sys.path.insert(0, r'C:\papki\work\bets\delux')

from db import get_db_connection

with get_db_connection() as conn:
    # Get today's football matches
    rows = conn.execute("""
        SELECT m.match_id, m.match_date, m.sport,
               ht.name as home, at.name as away,
               ms.form_json, ms.fetched_at
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        LEFT JOIN match_snapshot ms ON m.match_id = ms.match_id
        WHERE m.match_date LIKE '2026.09.16%'
          AND m.sport = 1
        ORDER BY m.match_date
    """).fetchall()
    
    print(f"Today's football matches: {len(rows)}")
    print()
    
    missing_form = 0
    has_form = 0
    
    for r in rows:
        d = dict(r)
        match_id = d['match_id']
        home = d['home'] or ''
        away = d['away'] or ''
        form_json = d['form_json']
        fetched_at = d['fetched_at']
        
        if form_json and form_json.strip() != 'None' and form_json.strip() != '':
            has_form += 1
            print(f"  ✓ {match_id} | {home[:25]:25s} vs {away[:25]:25s} | fetched={fetched_at}")
        else:
            missing_form += 1
            print(f"  ✗ {match_id} | {home[:25]:25s} vs {away[:25]:25s} | NO FORM DATA")
    
    print(f"\nSummary:")
    print(f"  With form: {has_form}")
    print(f"  Missing form: {missing_form}")
