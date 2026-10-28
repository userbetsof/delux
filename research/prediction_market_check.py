import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from odds_normalize import market_key, prediction_market

cases = [
    "ТБ 1,5",
    "ТБ2.5",
    "ТБ 8,5",
    "ТМ 2,5",
    "ТБ",
    "ТБ -0,5",
    "П1",
    "П2",
    "1",
    "2",
    "X",
    "Х",
    "1X",
    "1Х",
    "X2",
    "Х2",
    "12",
    "ОЗ",
    "Обе Забьют (ОЗ)",
    "Ф1(0)",
    "Ф2(0)",
    "1X + ТБ 2,5",
    "1:1 / X",
    "Х П2",
    "-",
    "0",
]
for c in cases:
    m = prediction_market(c)
    print(f"{c!r:20} -> {m!r:22} key={market_key(m) if m else None}")

print("--- market_key сравнения")
for a, b in [
    ("HANDICAP HOME 0.0", "HANDICAP HOME 0"),
    ("OVER 1.5", "OVER 1,5"),
    ("DC_12", "DC_12"),
    ("1X2_1", "1X2_1"),
    ("HANDICAP AWAY -1.0", "HANDICAP AWAY -1"),
]:
    print(a, "|", b, "->", market_key(a) == market_key(b))
