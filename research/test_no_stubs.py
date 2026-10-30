import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

import flashscore_feed

flashscore_feed._MAIN_HOST_DEAD = True

from settings import DeluxSettings
from analysis_data import MatchInfo, build_settings, load_analysis_data
from calc_backend import get_calc_engine
from odds_service import load_odds

cfg = DeluxSettings.from_env()
ms = build_settings(
    sport=1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

MID = "WzuV5eoq"
info = MatchInfo(match_id=MID)
info.status = "3"
info.start_ts = 1439042700

full = load_analysis_data(info, ms)
print(
    "загружено: home_all=%d home_home=%d home_away=%d away_all=%d h2h=%d"
    % (
        len(full.home_all), len(full.home_home), len(full.home_away),
        len(full.away_all), len(full.h2h),
    )
)

cut = "2015.08.08 14:45"
full.home_all = [h for h in full.home_all if str(h.date) < cut]
full.away_all = [h for h in full.away_all if str(h.date) < cut]
full.h2h = [h for h in full.h2h if str(h.date) < cut]
print(f"после обрезки: home_all={len(full.home_all)} away_all={len(full.away_all)}")

full.settings = ms
full.match = info

_c, odds_data = load_odds(MID, cfg.source)
res = get_calc_engine(cfg).run(full, odds_data, list_odds=[])
names = ["1 пр", "2 пр", "de lux", "poisson", "ср взвеш", "mill", "Mini Vini", "Elizabet", "5Match p", "5Match"]
print()
for i, p in enumerate(res.get("outcome_probabilities") or []):
    h, d, a = p.get("home_prob", 0), p.get("draw_prob", 0), p.get("away_prob", 0)
    print(f"  {names[i]:10}: {h:.3f}/{d:.3f}/{a:.3f}{'  << НОЛЬ' if h+d+a==0 else ''}")
