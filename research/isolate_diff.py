import sys
import time

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

print("объёмы полной загрузки после обрезки:")
print(f"  home_all={len(full.home_all)} home_home={len(full.home_home)} home_away={len(full.home_away)}")
print(f"  away_all={len(full.away_all)} away_home={len(full.away_home)} away_away={len(full.away_away)}")
print(f"  h2h={len(full.h2h)} h2h_home={len(full.h2h_home)}")


def run(p, label):
    p.settings = ms
    p.match = info
    t0 = time.time()
    res = eng.run(p, odds_data, list_odds=[])
    el = time.time() - t0
    n = sum(
        1
        for x in (res.get("outcome_probabilities") or [])
        if (x.get("home_prob") or 0) + (x.get("draw_prob") or 0) + (x.get("away_prob") or 0) > 0
    )
    print(f"  {label}: {n}/10 за {el:.1f}s", flush=True)
    return n


print("\nэксперименты:")
run(full, "полные данные")

# Обрезаем до 34, как в снимке
saved = (full.home_all, full.home_home, full.home_away,
         full.away_all, full.away_home, full.away_away)
full.home_all = full.home_all[-34:]
full.home_home = full.home_home[-17:]
full.home_away = full.home_away[-17:]
full.away_all = full.away_all[-36:]
full.away_home = full.away_home[-19:]
full.away_away = full.away_away[-17:]
run(full, "обрезано как в снимке")
full.home_all, full.home_home, full.home_away, full.away_all, full.away_home, full.away_away = saved

# Без h2h_home
saved_h2h = full.h2h_home
full.h2h_home = []
run(full, "без h2h_home")
full.h2h_home = saved_h2h
