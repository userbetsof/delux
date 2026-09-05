import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import MatchInfo, build_settings, load_analysis_data
from calc_engine import ExcelCalcEngine
from odds_service import load_odds
from settings import DeluxSettings

mid = sys.argv[1]
cfg = DeluxSettings.from_env()
wb = cfg.resolve_calc_workbook()
conn = sqlite3.connect("matches.db")
conn.row_factory = sqlite3.Row
row = conn.execute(
    """
    SELECT m.sport, m.match_date, ht.name AS home, at.name AS away,
           c.name AS country, l.name AS league
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
payload = load_analysis_data(match, ms)
_, odds = load_odds(mid, cfg.source)
print("payload", len(payload.h2h), len(payload.home_all))

with ExcelCalcEngine(wb) as eng:
    eng.wb.Worksheets("Старт").Range("R2").Value = row["sport"]
    eng.write_payload(payload)
    eng.write_odds(odds)
    eng.calculate()
    inc = eng.wb.Worksheets("Incognito DATA")
    poi = eng.wb.Worksheets("Poisson")
    print("S6", inc.Range("S6").Value, "B13", poi.Range("B13").Value)
    an = eng.wb.Worksheets("Анализ")
    for row_num in (8, 10, 12, 14, 16, 18, 20):
        print(
            f"row {row_num}",
            an.Range(f"H{row_num}").Value,
            an.Range(f"J{row_num}").Value,
            an.Range(f"K{row_num}").Value,
        )
