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
res = get_calc_engine(cfg).run(full, odds_data, list_odds=[])

names = [
    "1 пр", "2 пр", "de lux", "poisson", "ср взвеш",
    "mill", "Mini Vini", "Elizabet", "5Match p", "5Match",
]
print("ПОЛНАЯ ЗАГРУЗКА, результат движка:")
for i, p in enumerate(res.get("outcome_probabilities") or []):
    h, d, a = p.get("home_prob", 0), p.get("draw_prob", 0), p.get("away_prob", 0)
    mark = "  << НОЛЬ" if h + d + a == 0 else ""
    print(f"  {names[i] if i < len(names) else i:10}: {h:.3f}/{d:.3f}/{a:.3f}{mark}")

print()
print("ДЛИНА ИСТОРИИ в полной загрузке:")
print("  home_all:", len(full.home_all))
print("  away_all:", len(full.away_all))
print()
print("Сколько матчей реально нужно движку — проверим по последним 40:")
print("  home_all[-40:]:", len(full.home_all[-40:]))
