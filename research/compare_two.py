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
rec._skip_slow_page_fetch()
rec._skip_daily_feed_lookup()

from settings import DeluxSettings
from analysis_data import HistoryMatch
from calc_backend import get_calc_engine
from odds_service import load_odds

cfg = DeluxSettings.from_env()
ms = rec_build = None
from analysis_data import build_settings

ms = build_settings(
    sport=1, source=cfg.source, tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset,
)

names = ["1 пр", "2 пр", "de lux", "poisson", "ср взвеш", "mill", "Mini Vini", "Elizabet", "5Match p", "5Match"]


def to_hm(item):
    return HistoryMatch(**{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__})


for MID, cut in (("Qg22AywS", "2015.08.08 17:00"), ("WzuV5eoq", "2015.08.08 14:45")):
    payload = rec._payload_from_snapshot(MID, 1, cfg)
    hist = rec._history_from_snapshot(MID)
    payload.h2h = [to_hm(x) for x in hist["h2h"] if str(x.get("date") or "") < cut]
    payload.h2h_home = [to_hm(x) for x in hist["h2h_home"] if str(x.get("date") or "") < cut]
    payload.home_all = [to_hm(x) for x in hist["home_all"] if str(x.get("date") or "") < cut]
    payload.away_all = [to_hm(x) for x in hist["away_all"] if str(x.get("date") or "") < cut]
    payload.home_home = []
    payload.home_away = []
    payload.away_home = []
    payload.away_away = []
    payload.settings = ms
    from analysis_data import MatchInfo

    payload.match = MatchInfo(match_id=MID)
    payload.match.status = "3"

    _c, od = load_odds(MID, cfg.source)
    res = get_calc_engine(cfg).run(payload, od, list_odds=[])
    print(f"\n{MID} (h2h={len(payload.h2h)} home={len(payload.home_all)} away={len(payload.away_all)}):")
    for i, p in enumerate(res.get("outcome_probabilities") or []):
        h, d, a = p.get("home_prob", 0), p.get("draw_prob", 0), p.get("away_prob", 0)
        print(f"  {names[i]:10}: {h:.3f}/{d:.3f}/{a:.3f}{'  << НОЛЬ' if h+d+a==0 else ''}")
