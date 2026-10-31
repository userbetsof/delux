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

from settings import DeluxSettings
from analysis_data import MatchInfo, build_settings, HistoryMatch
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

MID = "ncRVhYJ7"
payload = rec._payload_from_snapshot(MID, 1, cfg)
hist = rec._history_from_snapshot(MID)


def to_hm(item):
    return HistoryMatch(**{k: item.get(k, "") for k in HistoryMatch.__dataclass_fields__})


payload.h2h = [to_hm(x) for x in hist["h2h"]]
payload.h2h_home = [to_hm(x) for x in hist["h2h_home"]]
payload.home_all = [to_hm(x) for x in hist["home_all"]]
payload.away_all = [to_hm(x) for x in hist["away_all"]]
payload.home_home = []
payload.home_away = []
payload.away_home = []
payload.away_away = []
payload.settings = ms
payload.match = MatchInfo(match_id=MID)
payload.match.status = "1"
_h, _a = rec._team_names_of(MID)
payload.match.home = _h
payload.match.away = _a
print(f"команды: {_h!r} - {_a!r}")

_c, odds_data = load_odds(MID, cfg.source)

eng = get_calc_engine(cfg)

# подменяем run, чтобы получить доступ к store после расчёта
store_holder = {}
orig_build = getattr(eng, "_build_store", None)
if orig_build:
    def patched(*a, **kw):
        store = orig_build(*a, **kw)
        store_holder["store"] = store
        return store

    eng._build_store = patched

# проверим константы ДО run
c=eng._load_constants()
print("ДО run: Очные!A1 = " + repr(c.get("Очные",{}).get("A1")))
print("ДО run: Таблица!B2 = " + repr(c.get("Таблица",{}).get("B2")))
res = eng.run(payload, odds_data, list_odds=[])
store = store_holder.get("store")

if store is None:
    print("store не получен")
    raise SystemExit(1)


def val(sheet, ref):
    try:
        k = store.key(sheet, ref)
        if k in store._values:
            return store._values[k]
        return "<нет>"
    except Exception as e:
        return f"<err {e}>"


print("Графики — свёртки Пуассона:")
for ref in ("T25","R25","R27","R32","R39","R44","S46","S47","S49","U46","X26","X28","W37","Y37"):
    print(f"  {ref} = {val('Графики', ref)}")

print()
print("слагаемые AO:")
total = {}
for start, end, name in ((42, 69, "M26 хозяева"), (73, 100, "M27 гости"), (104, 110, "M28 ничья")):
    s = 0.0
    zero = 0
    for r in range(start, end + 1):
        v = val("Графики", f"AO{r}")
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.0
            zero += 1
        s += f
    total[name] = s / 100
    print(f"  {name} (AO{start}:AO{end}) = {s:.4f} → {s/100*100:.2f}%  (нечитаемых {zero})")

print()
print("ключи store, содержащие Очные:")
hits=[k for k in store._values if 'Очные' in k][:8]
for k in hits:
    print(f"  {k} = {store._values[k]!r}")
print(f"  всего: {len([k for k in store._values if 'Очные' in k])}")
print()
print("Очные — ключи:")
for ref in ("A1","B1"):
    print(f"  Очные!{ref} = {val('Очные', ref)!r}")
print("  Таблица!B2 = ", val("Таблица", "B2"))
print()
print("проверка диапазона Таблица B2:G45:")
for r in (2,19):
    row=[store.get("Таблица", f"{c}{r}") for c in "BCDEFG"]
    print(f"  стр.{r}:", row)
print()
tv = store.get_range("Таблица", 2, 2, 45, 7) if hasattr(store,'get_range') else None


print()
print("Mill — цепочка расчёта:")
for ref in ("W37","X39","Y37","X26","X28","S49","T25","R25","R27","R39","S46","P24","P36"):
    v = val("Mill", ref)
    print(f"  Mill!{ref} = {v!r}")

print()
print("первые AO и их источники:")
for r in (42,43,44,73,74,75):
    ao = val("Графики", f"AO{r}")
    am = val("Графики", f"AM{r}")
    an = val("Графики", f"AN{r}")
    ak = val("Графики", f"AK{r}")
    al = val("Графики", f"AL{r}")
    print(f"  AO{r}: ak={ak!r} al={al!r} am={am!r} an={an!r} ao={ao!r}")
