import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

from analysis_data import MatchInfo, build_settings, load_analysis_data, HistoryMatch
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


def count(p, label):
    p.settings = ms
    p.match = info
    res = eng.run(p, odds_data, list_odds=[])
    n = sum(
        1
        for x in (res.get("outcome_probabilities") or [])
        if (x.get("home_prob") or 0) + (x.get("draw_prob") or 0) + (x.get("away_prob") or 0) > 0
    )
    print(f"  {label}: {n}/10", flush=True)
    return n


# --- ПОЛНАЯ
full = load_analysis_data(info, ms)
cut = "2015.08.08 17:05"
full.home_all = [h for h in full.home_all if str(h.date) < cut]
full.away_all = [h for h in full.away_all if str(h.date) < cut]
full.h2h = [h for h in full.h2h if str(h.date) < cut]
count(full, f"полная (home_all={len(full.home_all)} away_all={len(full.away_all)} h2h={len(full.h2h)})")

# --- БЫСТРАЯ: весь payload из снимка
payload = rec._payload_from_snapshot("KdLPRx82", 1, cfg)
hist = rec._history_from_snapshot("KdLPRx82")


def to_hm(item):
    return HistoryMatch(**{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__})


payload.h2h = [to_hm(x) for x in hist["h2h"]]
payload.h2h_home = [to_hm(x) for x in hist["h2h_home"]]
payload.home_all = [to_hm(x) for x in hist["home_all"]]
payload.away_all = []
count(payload, f"снимок (home_all={len(payload.home_all)} away_all={len(payload.away_all)} h2h={len(payload.h2h)})")

# --- ГИБРИД: таблица+форма из снимка, история из полной
hybrid = rec._payload_from_snapshot("KdLPRx82", 1, cfg)
hybrid.h2h = full.h2h[:]
hybrid.h2h_home = full.h2h_home[:]
hybrid.home_all = full.home_all[:]
hybrid.home_home = full.home_home[:]
hybrid.home_away = full.home_away[:]
hybrid.away_all = full.away_all[:]
hybrid.away_home = full.away_home[:]
hybrid.away_away = full.away_away[:]
count(hybrid, "гибрид (таблица из снимка + история полная)")
