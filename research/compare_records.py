import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from analysis_data import MatchInfo, build_settings, load_analysis_data
from settings import DeluxSettings

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
cut = "2015.08.08 17:05"
full.home_all = [h for h in full.home_all if str(h.date) < cut]

snap = rec._history_from_snapshot("KdLPRx82")

print("=== ПОЛНАЯ home_all[-5:] ===")
for h in full.home_all[-5:]:
    print(f"  {h.date} | {h.home_name} - {h.away_name} | ht={h.home_ht}-{h.away_ht} st={h.home_st}-{h.away_st} venue={h.venue!r}")

print()
print("=== СНИМОК home_all[-5:] ===")
for h in snap["home_all"][-5:]:
    print(f"  {h.get('date')} | {h.get('home_name')} - {h.get('away_name')} | ht={h.get('home_ht')}-{h.get('away_ht')} st={h.get('home_st')}-{h.get('away_st')} venue={h.get('venue')!r}")

print()
print("=== ЕСТЬ ЛИ 'ВЕСТ БРОМВИЧ' В СНИМКЕ? ===")
names = {h.get("home_name") for h in snap["home_all"]} | {h.get("away_name") for h in snap["home_all"]}
print("  ", [n for n in names if "Бром" in str(n)])
print("  всего уникальных команд:", len(names))
print("  примеры:", list(names)[:5])
