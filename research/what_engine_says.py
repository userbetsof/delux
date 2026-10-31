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
rec._install_feed_cache()

from settings import DeluxSettings

cfg = DeluxSettings.from_env()
probs = rec._recalc_one("ncRVhYJ7", cfg)

names = [
    "1 пр", "2 пр", "de lux", "poisson", "ср взвеш",
    "mill", "Mini Vini", "Elizabet", "5Match p", "5Match",
]
print("движок сейчас:")
for i, p in enumerate(probs or []):
    h = (p.get("home_prob") or 0) * 100
    d = (p.get("draw_prob") or 0) * 100
    a = (p.get("away_prob") or 0) * 100
    print(f"  {names[i]:10}: {h:6.1f} / {d:6.1f} / {a:6.1f}  (Σ {h+d+a:5.1f})")
