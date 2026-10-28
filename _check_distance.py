import sqlite3

conn = sqlite3.connect('matches.db')

# Проверим структуру teams
cursor = conn.execute("PRAGMA table_info(teams)")
print('teams columns:')
for c in cursor.fetchall():
    print(f'  {c}')

# Проверим есть ли venue_id у команд
cursor = conn.execute("SELECT id, name, venue_id FROM teams WHERE venue_id IS NOT NULL LIMIT 10")
rows = cursor.fetchall()
print(f'\nTeams with venue_id: {len(rows)}')
for r in rows:
    print(f'  {r}')

# Проверим venues
cursor = conn.execute("SELECT * FROM venues LIMIT 5")
print('\nVenues sample:')
for r in cursor.fetchall():
    print(f'  {r}')

# Проверим venue_distances
cursor = conn.execute("SELECT COUNT(*) as cnt FROM venue_distances")
print(f'\nVenue distances count: {cursor.fetchone()[0]}')

# Проверим match_snapshot distance
cursor = conn.execute("SELECT COUNT(*) as cnt FROM match_snapshot WHERE distance IS NOT NULL")
print(f'Match snapshot with distance: {cursor.fetchone()[0]}')

conn.close()
