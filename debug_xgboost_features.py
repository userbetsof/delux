"""Debug why XGBoost returns None for most matches."""
import sys
sys.path.insert(0, r'C:\papki\work\bets\delux')

from db import get_db_connection
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog

with get_db_connection() as conn:
    rows = conn.execute("""
        SELECT m.match_id, m.match_date, ht.name as home, at.name as away
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        WHERE m.match_date LIKE '2026.09.16%'
          AND m.sport = 1
        ORDER BY m.match_date
    """).fetchall()
    
    print(f"Today's football matches: {len(rows)}")
    
    # Build dataset
    dataset = build_feature_dataset(DatabaseCatalog(), training=False, include_stacking=False)
    
    print(f"\nDataset rows: {len(dataset.frame)}")
    print(f"Features: {len(dataset.feature_columns)}")
    
    # Check which matches are in dataset
    for r in rows:
        d = dict(r)
        match_id = d['match_id']
        home = d['home'] or ''
        away = d['away'] or ''
        
        in_dataset = match_id in dataset.frame['match_id'].values
        print(f"  {match_id} | {home[:20]:20s} vs {away[:20]:20s} | in_dataset={in_dataset}")
        
        if in_dataset:
            row = dataset.frame[dataset.frame['match_id'] == match_id]
            if not row.empty:
                print(f"    Features count: {len(dataset.feature_columns)}")
                # Check if key features exist
                key_features = ['implied_p1', 'implied_px', 'implied_p2', 'implied_over_2_5']
                for f in key_features:
                    val = row[f].values[0] if f in row.columns else 'N/A'
                    print(f"      {f}: {val}")
