import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import build_settings, load_analysis_data
from calc_engine import ExcelCalcEngine
from match_store import get_queued_match
from odds_service import load_odds
from settings import DeluxSettings

mid = sys.argv[1]
cfg = DeluxSettings.from_env()
wb = cfg.resolve_calc_workbook()
queued = get_queued_match(mid)
if not queued:
    raise SystemExit("not in queue")
match = queued.to_match_info()
ms = build_settings(
    sport=queued.sport,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)
_, odds = load_odds(mid, cfg.source)
payload = load_analysis_data(match, ms)
print(
    "payload",
    len(payload.h2h),
    len(payload.home_all),
    len(payload.table_overall),
)

SOURCES = [
    ("strat1", "Анализ", "H8", "J8", "K8"),
    ("strat1-src", "Incognito DATA", "S6", "T6", "U6"),
    ("strat2-src", "Incognito DATA", "W6", "X6", "Y6"),
    ("strat4-src", "Poisson", "B13", "C13", "D13"),
    ("strat6-src", "Mill", "W37", "X39", "Y37"),
    ("strat7-src", "Incognito DATA", "J13", "K13", "L13"),
]

with ExcelCalcEngine(wb) as eng:
    eng.wb.Worksheets("Старт").Range("R2").Value = queued.sport
    eng.wb.Worksheets("Старт").Range("X2").Value = cfg.source
    eng.write_payload(payload)
    eng.write_odds(odds)
    eng.calculate()
    for name, sheet, h, d, a in SOURCES:
        ws = eng.wb.Worksheets(sheet)
        print(name, ws.Range(h).Value, ws.Range(d).Value, ws.Range(a).Value)

    inc = eng.wb.Worksheets("Incognito DATA")
    for addr in ("A1", "A7", "I3", "I10", "B3", "C3", "D3", "B10", "C10", "T32", "T34", "P16"):
        print("inc", addr, inc.Range(addr).Value)

    poi = eng.wb.Worksheets("Poisson")
    print("poi G13 I7", poi.Range("G13").Value, poi.Range("I7").Value)
