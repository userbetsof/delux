import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import flashscore_feed

flashscore_feed._MAIN_HOST_DEAD = True

import analysis_data as ad
from settings import DeluxSettings

cfg = DeluxSettings.from_env()
ms = ad.build_settings(
    sport=1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

MID = "Kbfus9D6"

# Профилируем отдельные функции, которые зовёт load_analysis_data
for name in (
    "fetch_table",
    "fetch_h2h",
    "fetch_team_history",
    "fetch_match_info",
):
    fn = getattr(ad, name, None)
    if fn is None:
        print(f"{name}: нет функции")
        continue
    t0 = time.time()
    try:
        if name == "fetch_team_history":
            r = fn(ms, MID, "Вест Бромвич")
        elif name == "fetch_h2h":
            r = fn(ms, MID)
        else:
            r = fn(ms, MID)
        n = len(r) if hasattr(r, "__len__") else "-"
    except Exception as exc:  # noqa: BLE001
        n = f"ERR {type(exc).__name__}"
    print(f"{name}: {time.time()-t0:6.1f}s -> {n}", flush=True)
