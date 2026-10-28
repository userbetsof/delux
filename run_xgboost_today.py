"""Run XGBoost strategy on today's matches."""
import sys
sys.path.insert(0, r'C:\papki\work\bets\delux')

from db import get_db_connection, upsert_strategy_prediction
from src.strategies import get_strategy
from src.strategies.base import MatchContext

# Get today's matches
with get_db_connection() as conn:
    rows = conn.execute("""
        SELECT m.match_id, m.sport, ht.name as home, at.name as away
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        WHERE m.match_date LIKE '2026.09.16%'
          AND m.match_status != 'Завершен'
          AND m.sport = 1
        ORDER BY m.match_date
    """).fetchall()
    
    print(f"Today's football matches: {len(rows)}")
    
    # Get XGBoost strategy
    xgboost = get_strategy(10)
    
    processed = 0
    signals = 0
    
    for row in rows:
        d = dict(row)
        match_id = d['match_id']
        sport = int(d['sport'] or 1)
        home = d['home'] or ''
        away = d['away'] or ''
        
        ctx = MatchContext(
            match_id=match_id,
            home=home,
            away=away,
            sport=sport,
        )
        
        signal = xgboost.evaluate(ctx)
        processed += 1
        
        if signal:
            signals += 1
            print(f"  SIGNAL: {match_id} | {home[:25]:25s} vs {away[:25]:25s} | {signal.prediction} @ {signal.odds:.2f} | prob={signal.extra.get('probability', 0):.3f}")
            
            # Save to DB
            upsert_strategy_prediction(
                match_id,
                10,
                signal.prediction,
                odds=signal.odds,
                notes=signal.notes,
            )
        else:
            print(f"  SKIP: {match_id} | {home[:25]:25s} vs {away[:25]:25s}")
    
    print(f"\nProcessed: {processed}, Signals: {signals}")
