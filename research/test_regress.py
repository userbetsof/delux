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

from settings import DeluxSettings

cfg = DeluxSettings.from_env()

# сравниваем три варианта
for label, skip_daily in (("с дневными лентами", False), ("без дневных лент", True)):
    if skip_daily:
        rec._skip_slow_page_fetch()
        rec._skip_daily_feed_lookup()
    else:
        rec._skip_slow_page_fetch()
    probs = rec._recalc_one("WzuV5eoq", cfg)
    n = sum(
        1
        for x in (probs or [])
        if sum(x.get(k, 0) for k in ("home_prob", "draw_prob", "away_prob")) > 0
    )
    print(f"{label}: {n}/10", flush=True)
