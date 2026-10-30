import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from analysis_data import MatchInfo, build_settings, HistoryMatch
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

_c, odds_data = load_odds("KdLPRx82", cfg.source)
eng = get_calc_engine(cfg)

payload = rec._payload_from_snapshot("KdLPRx82", 1, cfg)
hist = rec._history_from_snapshot("KdLPRx82")


def to_hm(item):
    return HistoryMatch(**{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__})


payload.h2h = [to_hm(x) for x in hist["h2h"]]
payload.home_all = [to_hm(x) for x in hist["home_all"]]
payload.away_all = [to_hm(x) for x in hist["away_all"]]
payload.settings = ms
payload.match = info

print("порядок home_all (первые 3 / последние 3):")
for h in payload.home_all[:3]:
    print(f"  {h.date} {h.home_name}")
print("  ...")
for h in payload.home_all[-3:]:
    print(f"  {h.date} {h.home_name}")

res = eng.run(payload, odds_data, list_odds=[])
names = ["1 пр", "2 пр", "de lux", "poisson", "ср взвеш", "mill", "Mini Vini", "Elizabet", "5Match p", "5Match"]
print()
for i, p in enumerate(res.get("outcome_probabilities") or []):
    h, d, a = p.get("home_prob", 0), p.get("draw_prob", 0), p.get("away_prob", 0)
    print(f"  {names[i]:10}: {h:.3f}/{d:.3f}/{a:.3f}{'  << НОЛЬ' if h+d+a==0 else ''}")
