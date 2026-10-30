import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

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
info = MatchInfo(match_id="KdLPRx82")
info.status = "3"
info.start_ts = 1439042700

full = load_analysis_data(info, ms)
_c, odds_data = load_odds("KdLPRx82", cfg.source)
eng = get_calc_engine(cfg)


def run_and_count(p, label):
    p.settings = ms
    p.match = info
    res = eng.run(p, odds_data, list_odds=[])
    n = sum(
        1
        for x in (res.get("outcome_probabilities") or [])
        if (x.get("home_prob") or 0) + (x.get("draw_prob") or 0) + (x.get("away_prob") or 0) > 0
    )
    print(f"  {label}: ненулевых {n}/10", flush=True)
    return n


cut = "2015.08.08 17:05"
full.home_all = [h for h in full.home_all if str(h.date) < cut]
full.away_all = [h for h in full.away_all if str(h.date) < cut]
full.h2h = [h for h in full.h2h if str(h.date) < cut]

print("объёмы после обрезки:")
print(f"  home_all={len(full.home_all)} away_all={len(full.away_all)} h2h={len(full.h2h)}")

print("\nэксперименты:")
run_and_count(full, "всё как есть")

# 1. хватает ли только 40 последних
saved = (full.home_all, full.away_all, full.h2h)
full.home_all = full.home_all[-40:]
full.away_all = full.away_all[-40:]
run_and_count(full, "только последние 40")

# 2. что если обнулить h2h
full.home_all, full.away_all, full.h2h = saved
saved2 = full.h2h
full.h2h = []
run_and_count(full, "без h2h")
full.h2h = saved2

# 3. без home_home/home_away (разбивка по сторонам)
saved3 = (full.home_home, full.home_away)
full.home_home = []
full.home_away = []
run_and_count(full, "без home_home/home_away")
full.home_home, full.home_away = saved3
