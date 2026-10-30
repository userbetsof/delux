import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

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
print("ПОЛНАЯ ЗАГРУЗКА")
print("  h2h:", len(full.h2h))
print("  home_all:", len(full.home_all))
print("  away_all:", len(full.away_all))
if full.home_all:
    h = full.home_all[0]
    print("  пример home_all[0]:")
    print(f"    home_name={h.home_name} away_name={h.away_name}")
    print(f"    home_ht={h.home_ht} away_ht={h.away_ht}")
    print(f"    home_st={h.home_st} away_st={h.away_st}")
    print(f"    venue={h.venue!r}")
if full.h2h:
    h = full.h2h[0]
    print("  пример h2h[0]:")
    print(f"    home_name={h.home_name} home_st={h.home_st} away_st={h.away_st} venue={h.venue!r}")
