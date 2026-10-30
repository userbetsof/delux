import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

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

import datetime

kickoff = datetime.datetime.fromtimestamp(1439042700).strftime("%Y.%m.%d %H:%M")
print("дата матча:", kickoff)
print("всего home_all:", len(full.home_all))
before = [h for h in full.home_all if str(h.date) < kickoff]
after = [h for h in full.home_all if str(h.date) >= kickoff]
print(f"  до матча: {len(before)}")
print(f"  после/на дату: {len(after)}   <-- утечка будущего")
if after:
    print("  пример будущего:", after[0].date, after[0].home_name)
