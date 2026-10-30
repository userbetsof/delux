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
full.settings = ms
full.match = info
_c, odds_data = load_odds("KdLPRx82", cfg.source)

names = [
    "1 пр", "2 пр", "de lux", "poisson", "ср взвеш",
    "mill", "Mini Vini", "Elizabet", "5Match p", "5Match",
]


def count_nonzero(res):
    return sum(
        1
        for p in (res.get("outcome_probabilities") or [])
        if (p.get("home_prob") or 0)
        + (p.get("draw_prob") or 0)
        + (p.get("away_prob") or 0)
        > 0
    )


eng = get_calc_engine(cfg)

for n in (40, 100, 200, 400, 959):
    full.home_all = full.home_all[:n] if n < len(full.home_all) else full.home_all
    res = eng.run(full, odds_data, list_odds=[])
    print(f"home_all обрезан до {len(full.home_all)}: ненулевых {count_nonzero(res)}/10", flush=True)
