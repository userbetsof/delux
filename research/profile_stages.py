import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import flashscore_feed

flashscore_feed._MAIN_HOST_DEAD = True

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from analysis_data import MatchInfo, build_settings, load_analysis_data
from calc_backend import get_calc_engine
from odds_service import load_odds
from settings import DeluxSettings

cfg = DeluxSettings.from_env()
ms = build_settings(
    sport=1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

MID = "Kbfus9D6"

t0 = time.time()
payload = rec._payload_from_snapshot(MID, 1, cfg)
t_snap = time.time() - t0

t0 = time.time()
_c, odds_data = load_odds(MID, cfg.source)
t_odds = time.time() - t0

info = MatchInfo(match_id=MID)
info.status = "3"
t0 = time.time()
full = load_analysis_data(info, ms)
t_full = time.time() - t0

cut = "2015.08.08 17:05"
full.home_all = [h for h in full.home_all if str(h.date) < cut]
full.settings = ms
full.match = info

t0 = time.time()
res = get_calc_engine(cfg).run(full, odds_data, list_odds=[])
t_eng = time.time() - t0

print(f"снимок:   {t_snap:6.1f}s")
print(f"odds:     {t_odds:6.1f}s")
print(f"полная:   {t_full:6.1f}s   <-- узкое место")
print(f"движок:   {t_eng:6.1f}s")
print(f"ИТОГО:    {t_snap+t_odds+t_full+t_eng:6.1f}s")
