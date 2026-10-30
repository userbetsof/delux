import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

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
info = MatchInfo(match_id="KdLPRx82")
info.status = "3"
info.start_ts = 1439042700

full = load_analysis_data(info, ms)
_c, odds_data = load_odds("KdLPRx82", cfg.source)
eng = get_calc_engine(cfg)
cut = "2015.08.08 17:05"

full.home_all = [h for h in full.home_all if str(h.date) < cut]
full.away_all = [h for h in full.away_all if str(h.date) < cut]
full.h2h = [h for h in full.h2h if str(h.date) < cut]


def count(p):
    p.settings = ms
    p.match = info
    res = eng.run(p, odds_data, list_odds=[])
    return sum(
        1
        for x in (res.get("outcome_probabilities") or [])
        if (x.get("home_prob") or 0)
        + (x.get("draw_prob") or 0)
        + (x.get("away_prob") or 0)
        > 0
    )


import copy

base_home = full.home_all[:]
for n in (5, 10, 20, 30, 40):
    full.home_all = base_home[-n:]
    print(f"home_all[-{n}]: {count(full)}/10", flush=True)
