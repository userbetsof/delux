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

print("ПОЛНАЯ, последние 5:")
for h in full.home_all[-5:]:
    print(f"  {h.date} | {h.home_name} - {h.away_name} | venue={h.venue!r}")

print()
print("СНИМОК, последние 5:")
for h in snap["home_all"][-5:]:
    print(f"  {h.get('date')} | {h.get('home_name')} - {h.get('away_name')} | venue={h.get('venue')!r}")

print()
print("ПОЛНАЯ, ПЕРВЫЕ 5:")
for h in full.home_all[:5]:
    print(f"  {h.date} | {h.home_name} - {h.away_name}")

print()
print("СНИМОК, ПЕРВЫЕ 5:")
for h in snap["home_all"][:5]:
    print(f"  {h.get('date')} | {h.get('home_name')} - {h.get('away_name')}")

print()
full_dates = {str(h.date) for h in full.home_all}
snap_dates = {str(h.get("date")) for h in snap["home_all"]}
print(f"матчей в полной: {len(full_dates)}")
print(f"матчей в снимке: {len(snap_dates)}")
print(f"есть в обоих: {len(full_dates & snap_dates)}")
print(f"только в полной: {len(full_dates - snap_dates)}")
print(f"только в снимке: {len(snap_dates - full_dates)}")
