import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from settings import DeluxSettings
from analysis_data import MatchInfo, build_settings
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

MID = "KdLPRx82"

t0 = time.time()
payload = rec._payload_from_snapshot(MID, 1, cfg)
print(f"payload из снимка: {time.time()-t0:.2f}s", flush=True)

hist = rec._history_from_snapshot(MID)
print(
    "срезы: h2h=%d h2h_home=%d home_all=%d home_home=%d home_away=%d "
    "away_all=%d away_home=%d away_away=%d"
    % tuple(
        len(hist.get(k) or [])
        for k in (
            "h2h", "h2h_home", "home_all", "home_home",
            "home_away", "away_all", "away_home", "away_away",
        )
    ),
    flush=True,
)

from analysis_data import HistoryMatch


def to_hm(item):
    return HistoryMatch(**{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__})


payload.h2h = [to_hm(x) for x in hist["h2h"]]
payload.h2h_home = [to_hm(x) for x in hist["h2h_home"]]
for side in ("home", "away"):
    for part in ("all", "home", "away"):
        setattr(payload, f"{side}_{part}", [to_hm(x) for x in hist[f"{side}_{part}"]])

payload.settings = ms
info = MatchInfo(match_id=MID)
info.status = "3"
info.start_ts = 1439042700
payload.match = info

_c, odds_data = load_odds(MID, cfg.source)

t0 = time.time()
res = get_calc_engine(cfg).run(payload, odds_data, list_odds=[])
print(f"движок (быстрый путь): {time.time()-t0:.1f}s", flush=True)

n = sum(
    1
    for x in (res.get("outcome_probabilities") or [])
    if (x.get("home_prob") or 0) + (x.get("draw_prob") or 0) + (x.get("away_prob") or 0) > 0
)
print(f"ненулевых: {n}/10")
