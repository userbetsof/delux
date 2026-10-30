import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util
import time

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from analysis_data import MatchInfo, build_settings
from calc_backend import get_calc_engine
from odds_service import load_odds

MID = "KdLPRx82"

rec_cfg = None
from settings import DeluxSettings

cfg = DeluxSettings.from_env()
rec_cfg = cfg

ms = build_settings(
    sport=1,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

payload = rec._payload_from_snapshot(MID, 1, cfg)
print(
    "из снимка: table %d form %d h2h %d home %d away %d"
    % (
        len(payload.table_overall),
        len(payload.form_overall),
        len(payload.h2h),
        len(payload.home_all),
        len(payload.away_all),
    )
)

# Добавляем историю так же, как _recalc_one
from analysis_data import HistoryMatch

hist = rec._history_from_snapshot(MID)
print(
    "hist из снимка: h2h %d home %d away %d"
    % (len(hist["h2h"]), len(hist["home_all"]), len(hist["away_all"]))
)


def to_hm(item):
    if not isinstance(item, dict):
        return None
    try:
        return HistoryMatch(
            **{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__}
        )
    except Exception:
        return None


payload.h2h = [h for h in (to_hm(x) for x in hist["h2h"]) if h]
payload.home_all = [h for h in (to_hm(x) for x in hist["home_all"]) if h]
payload.away_all = [h for h in (to_hm(x) for x in hist["away_all"]) if h]
print(
    "в payload: h2h %d home %d away %d"
    % (len(payload.h2h), len(payload.home_all), len(payload.away_all))
)

payload.settings = ms
payload.match = MatchInfo(match_id=MID)

_c, odds_data = load_odds(MID, cfg.source)

t0 = time.time()
res = get_calc_engine(cfg).run(payload, odds_data, list_odds=[])
elapsed = time.time() - t0

names = [
    "1 пр", "2 пр", "de lux", "poisson", "ср взвеш",
    "mill", "Mini Vini", "Elizabet", "5Match p", "5Match",
]
print(f"\nдвижок: {elapsed:.1f}s")
for i, p in enumerate(res.get("outcome_probabilities") or []):
    h, d, a = p.get("home_prob", 0), p.get("draw_prob", 0), p.get("away_prob", 0)
    mark = "  << НОЛЬ" if h + d + a == 0 else ""
    print(f"  {names[i] if i < len(names) else i:10}: {h:.3f}/{d:.3f}/{a:.3f}{mark}")
