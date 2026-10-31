"""Трассировка цепочки Mill — что реально считает движок."""

import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

import flashscore_feed

flashscore_feed._MAIN_HOST_DEAD = True

import importlib.util

spec = importlib.util.spec_from_file_location(
    "rec", r"C:\papki\work\bets\delux\scripts\recalc_outcome_probs.py"
)
rec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rec)

rec._skip_slow_page_fetch()
rec._install_feed_cache()

from analysis_data import HistoryMatch, MatchInfo, build_settings
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

MID = "ncRVhYJ7"
payload = rec._payload_from_snapshot(MID, 1, cfg)
hist = rec._history_from_snapshot(MID)


def th(x):
    return HistoryMatch(**{k: x.get(k, "") for k in HistoryMatch.__dataclass_fields__})


payload.h2h = [th(x) for x in hist["h2h"]]
payload.h2h_home = [th(x) for x in hist["h2h_home"]]
payload.home_all = [th(x) for x in hist["home_all"]]
payload.home_home = [th(x) for x in hist["home_home"]]
payload.home_away = [th(x) for x in hist["home_away"]]
payload.away_home = [th(x) for x in hist["away_home"]]
payload.away_away = [th(x) for x in hist["away_away"]]
payload.away_all = [th(x) for x in hist["away_all"]]
payload.settings = ms
payload.match = MatchInfo(match_id=MID)
payload.match.status = "1"
_h, _a = rec._team_names_of(MID)
payload.match.home = _h
payload.match.away = _a

_c, odds_data = load_odds(MID, cfg.source)

eng = get_calc_engine(cfg)
holder = {}
orig = eng._build_store


def patched(*a, **kw):
    st = orig(*a, **kw)
    holder["store"] = st
    return st


eng._build_store = patched

res = eng.run(payload, odds_data, list_odds=[])
store = holder["store"]


def val(sheet, ref):
    k = store.key(sheet, ref)
    return store._values.get(k, "<нет>")


print(f"команды: {_h} - {_a}")
print()
print("Таблица — как видит движок:")
rows = {}
for col in ("A", "B", "C", "D", "E", "F", "G", "H"):
    for r in (2, 19):
        rows.setdefault(r, {})[col] = val("Таблица", f"{col}{r}")
for r in (2, 19):
    print(f"  стр.{r}: " + " | ".join(f"{c}={rows[r][c]!r}" for c in rows[r]))

print()
print("MAX(Таблица!A:A) =", val("Mill", "T25"))

print()
print("цепочка Mill:")
for ref in (
    "P24", "P36", "T25", "R25", "R27", "R39", "R32", "R44", "R29",
    "S46", "S47", "S49", "X26", "X28", "U46", "W37", "Y37", "X39",
):
    print(f"  Mill!{ref:4} = {val('Mill', ref)!r}")

print()
print("ДомаДома — строки 2-5, K/L/S:")
for r in (2,3,4,5):
    vals=[val("ДомаДома", f"{c}{r}") for c in ("I","K","L","S")]
    print(f"  стр.{r}: I={vals[0]!r} K={vals[1]!r} L={vals[2]!r} S={vals[3]!r}")
print("  R29 = ДомаДома!S4 =", val("Mill","R29"))
print()
print("итог Анализ!E18/I18/K18 (mill):")
for ref in ("E18", "I18", "K18"):
    v = val("Анализ", ref)
    try:
        print(f"  {ref} = {v!r}  →  {float(v)*100:.1f}%")
    except (TypeError, ValueError):
        print(f"  {ref} = {v!r}")
