import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import flashscore_feed

flashscore_feed._MAIN_HOST_DEAD = True

# Считаем все сетевые вызовы с их длительностью
orig = flashscore_feed.fetch_feed
stats = []


def timed(url, *a, **kw):
    t0 = time.time()
    try:
        r = orig(url, *a, **kw)
        stats.append((time.time() - t0, url.split("/")[-1], len(r)))
        return r
    except Exception:
        stats.append((time.time() - t0, url.split("/")[-1], -1))
        raise


flashscore_feed.fetch_feed = timed

import analysis_data

analysis_data.fetch_feed = timed

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

rec._skip_slow_page_fetch()
rec._skip_daily_feed_lookup()

from settings import DeluxSettings

cfg = DeluxSettings.from_env()

MID = sys.argv[1] if len(sys.argv) > 1 else "jJ2OpiEs"
t0 = time.time()
probs = rec._recalc_one(MID, cfg)
total = time.time() - t0

print(f"\n{MID}: всего {total:.0f}s")
print("сетевые вызовы:")
for el, name, size in sorted(stats, reverse=True)[:12]:
    print(f"  {el:6.1f}s  {name:40} {'ERR' if size < 0 else size}")
print(f"  сумма сети: {sum(s[0] for s in stats):.0f}s из {total:.0f}s")
