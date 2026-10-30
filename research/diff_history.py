import json
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

fast_hist = rec._history_from_snapshot("KdLPRx82")

print("=== ПОЛНАЯ home_all: последние 3 ===")
for h in full.home_all[-3:]:
    print(
        f"  {h.date} | {h.home_name} {h.home_ht}-{h.away_ht} {h.away_name} "
        f"| st={h.home_st}-{h.away_st} | venue={h.venue!r}"
    )

print()
print("=== СНИМОК home_all: последние 3 ===")
for h in fast_hist["home_all"][-3:]:
    print(
        f"  {h.get('date')} | {h.get('home_name')} {h.get('home_ht')}-{h.get('away_ht')} "
        f"{h.get('away_name')} | st={h.get('home_st')}-{h.get('away_st')} "
        f"| venue={h.get('venue')!r}"
    )

print()
print("=== ПОЛНАЯ h2h: первые 3 ===")
for h in full.h2h[:3]:
    print(f"  {h.date} | {h.home_name} - {h.away_name} | venue={h.venue!r}")

print()
print("=== СНИМОК h2h: первые 3 ===")
for h in fast_hist["h2h"][:3]:
    print(f"  {h.get('date')} | {h.get('home_name')} - {h.get('away_name')} | venue={h.get('venue')!r}")

print()
print("=== team_name для обрезки ===")
print("full.home_all[-1]:", full.home_all[-1].date, full.home_all[-1].home_name)
print("snap home_all[-1]:", fast_hist["home_all"][-1].get("date"), fast_hist["home_all"][-1].get("home_name"))
