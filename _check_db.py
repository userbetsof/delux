import sqlite3

conn = sqlite3.connect('matches.db')

# Структура teams
cursor = conn.execute("PRAGMA table_info(teams)")
print('teams columns:')
for c in cursor.fetchall():
    print(f'  {c}')

# Матч GEWpIqh4
cursor = conn.execute("SELECT home_team_id, away_team_id FROM matches WHERE match_id = ?", ('GEWpIqh4',))
home_id, away_id = cursor.fetchone()
print(f'\nMatch GEWpIqh4: home_id={home_id}, away_id={away_id}')

# Все команды с ID 136 и 145
cursor = conn.execute("SELECT * FROM teams WHERE id IN (136, 145)")
print('\nTeams 136 and 145:')
for r in cursor.fetchall():
    print(f'  {r}')

# Посмотрю все таблицы
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f'\nAll tables: {tables}')

conn.close()
