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

cfg = DeluxSettings.from_env()

for mid in ("KdLPRx82", "QgOXPGxF"):
    t0 = time.time()
    probs = rec._recalc_one(mid, cfg)
    elapsed = time.time() - t0
    nonzero = sum(
        1
        for x in (probs or [])
        if sum(x.get(k, 0) for k in ("home_prob", "draw_prob", "away_prob")) > 0
    )
    print(f"{mid}: {elapsed:.1f}s, ненулевых {nonzero}", flush=True)
