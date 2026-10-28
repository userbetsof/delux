import sqlite3

conn = sqlite3.connect('matches.db')

# ELO: сброс к 1500, матчей=0
conn.execute("""
    UPDATE team_elo_ratings 
    SET rating = 1500, matches_played = 0, wins = 0, losses = 0, draws = 0
""")
print(f"ELO: обновлено строк {conn.total_changes}")

# Glicko-2: сброс к rating=1500, RD=350, vol=0.6, матчей=0
conn.execute("""
    UPDATE glicko2_ratings 
    SET rating = 1500.0, rd = 350.0, volatility = 0.6, 
        matches_played = 0, wins = 0, losses = 0, draws = 0
""")
print(f"Glicko-2: обновлено строк {conn.total_changes}")

# OpenSkill: сброс к mu=3.0, sigma=1.0, матчей=0
conn.execute("""
    UPDATE openskill_ratings 
    SET mu = 3.0, sigma = 1.0,
        matches_played = 0, wins = 0, losses = 0, draws = 0
""")
print(f"OpenSkill: обновлено строк {conn.total_changes}")

conn.commit()

# Проверим
for table in ['team_elo_ratings', 'glicko2_ratings', 'openskill_ratings']:
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
    cnt = cursor.fetchone()[0]
    cursor = conn.execute(f"SELECT MIN(rating), MAX(rating), AVG(rating) FROM {table}")
    mn, mx, avg = cursor.fetchone()
    print(f"{table}: {cnt} строк, rating [{mn:.1f}..{mx:.1f}], avg={avg:.1f}")

conn.close()
print("\nГотово!")
