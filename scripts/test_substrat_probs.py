import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import MatchInfo, build_settings
from match_analysis import analyze_match
from settings import DeluxSettings

mid = sys.argv[1] if len(sys.argv) > 1 else "fZVsgwbs"
cfg = DeluxSettings.from_env()
wb = cfg.resolve_calc_workbook()

conn = sqlite3.connect("matches.db")
conn.row_factory = sqlite3.Row
row = conn.execute(
    """
    SELECT m.match_id, m.match_date, m.sport, ht.name AS home, at.name AS away,
           l.name AS league, c.name AS country
    FROM matches m
    JOIN teams ht ON ht.id = m.home_team_id
    JOIN teams at ON at.id = m.away_team_id
    JOIN leagues l ON l.id = m.league_id
    JOIN countries c ON c.id = l.country_id
    WHERE m.match_id = ?
    """,
    (mid,),
).fetchone()
conn.close()
if not row:
    raise SystemExit(f"match not found: {mid}")

ms = build_settings(
    sport=row["sport"],
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)
match = MatchInfo(
    match_id=mid,
    league=f"{row['country']}: {row['league']}",
    date=row["match_date"],
    home=row["home"],
    away=row["away"],
)
results = analyze_match(wb, match, ms, save_to_db=False)
for prob in results["outcome_probabilities"]:
    idx = prob["strategy_idx"] + 1
    print(
        f"strat {idx:2}: H={prob['home_prob']:.4f} "
        f"D={prob['draw_prob']:.4f} A={prob['away_prob']:.4f}"
    )
