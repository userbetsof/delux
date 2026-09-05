import os
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
ms = build_settings(
    sport=int(sys.argv[2]) if len(sys.argv) > 2 else 1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)
match = MatchInfo(
    match_id=mid,
    league=sys.argv[3] if len(sys.argv) > 3 else "",
    date="",
    home=sys.argv[4] if len(sys.argv) > 4 else "",
    away=sys.argv[5] if len(sys.argv) > 5 else "",
)
_, odds = load_odds(mid, cfg.source)
payload = load_analysis_data(match, ms)

with ExcelCalcEngine(wb) as eng:
    eng.write_payload(payload)
    eng.write_odds(odds)
    eng.calculate()
    mill = eng.wb.Worksheets("Mill")
    print("Mill W37 X39 Y37", mill.Range("W37").Value, mill.Range("X39").Value, mill.Range("Y37").Value)
    an = eng.wb.Worksheets("Анализ")
    print("Analysis H18 J18 K18", an.Range("H18").Value, an.Range("J18").Value, an.Range("K18").Value)
    print("history home rows", len(payload.home_all), "away", len(payload.away_all))
