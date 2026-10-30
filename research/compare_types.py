import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from settings import DeluxSettings
from analysis_data import MatchInfo, build_settings, load_analysis_data

cfg = DeluxSettings.from_env()
ms = build_settings(
    sport=1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)
info = MatchInfo(match_id="KdLPRx82")
info.status = "3"
info.start_ts = 1439042700
full = load_analysis_data(info, ms)

snap = rec._history_from_snapshot("KdLPRx82")

print("=== ТИПЫ ПОЛЕЙ ===")
f = full.home_all[0]
s = snap["home_all"][0] if snap["home_all"] else {}
for key in ("home_ht", "away_ht", "home_st", "away_st", "date", "venue"):
    fv = getattr(f, key, "<нет>")
    sv = s.get(key, "<нет>")
    print(f"  {key:9}: full={fv!r:8} ({type(fv).__name__:5})  snap={sv!r:8} ({type(sv).__name__})")

print()
print("=== ПОЛНАЯ: последний матч (после сортировки движка) ===")
print(f"  {full.home_all[-1].date} {full.home_all[-1].home_name}")
print("=== СНИМОК: последний матч (по возрастанию) ===")
if snap["home_all"]:
    last = snap["home_all"][-1]
    print(f"  {last.get('date')} {last.get('home_name')}")

print()
print("=== совпадает ли последний матч? ===")
same = snap["home_all"] and snap["home_all"][-1].get("date") == full.home_all[-1].date
print("  да" if same else "  НЕТ — разные данные")
