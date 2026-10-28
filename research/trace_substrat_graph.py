"""Полный граф зависимостей 10 подстратегий: какие входы и что статично."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

# Источники вероятностей 10 подстратегий (из calc_engine.extract_results: строки 8..26 листа Анализ)
# strategy_idx -> (sheet, home_cell, draw_cell, away_cell)
STRAT_SOURCES = [
    ("Анализ", "H8", "J8", "K8"),   # 0
    ("Анализ", "H10", "J10", "K10"),  # 1
    ("Анализ", "H12", "J12", "K12"),  # 2
    ("Анализ", "H14", "J14", "K14"),  # 3
    ("Анализ", "H16", "J16", "K16"),  # 4
    ("Анализ", "H18", "J18", "K18"),  # 5
    ("Анализ", "H20", "J20", "K20"),  # 6
    ("Анализ", "H22", "J22", "K22"),  # 7
    ("Анализ", "H24", "J24", "K24"),  # 8
    ("Анализ", "H26", "J26", "K26"),  # 9
]

# Имена подстратегий (в порядке id)
SUB_NAMES = ["1 пр", "2 пр", "de lux", "poisson", "ср взвеш", "mill", "Mini Vini", "Elizabet", "5Match p", "5Match"]

data = json.load(open("data/formulas_cache.json", encoding="utf-8"))
sheets = data.get("sheets", {})


def get_formula(sheet, addr):
    return sheets.get(sheet, {}).get(addr)


# Все листы с формулами
all_sheets = {k: v for k, v in sheets.items() if isinstance(v, dict)}


def refs_in(formula):
    """Извлечь ссылки вида Лист!Ячейка или Ячейка из формулы."""
    if not formula:
        return []
    # кросс-листовые: 'Имя листа'!A1  или Имя!A1
    out = []
    for m in re.finditer(r"([А-Яа-яA-Za-z][\w\s]*?)!([$]?[A-Z]{1,3}[$]?\d+)", formula):
        out.append((m.group(1).strip(), m.group(2).replace("$", "")))
    # локальные ссылки (без листа)
    for m in re.finditer(r"(?<![!\w])([$]?[A-Z]{1,3}[$]?\d+)", formula):
        cell = m.group(1).replace("$", "")
        # отсеять числа (50000, 100) — только буквы+цифра
        if re.fullmatch(r"[A-Z]{1,3}\d+", cell):
            out.append((None, cell))
    return out


def resolve_ref(sheet, addr):
    """Лист клетки и сама клетка; если sheet None — локальная в текущем листе."""
    return sheet, addr


# BFS от каждого исхода подстратегии, собираем листья (ячейки без формулы = входы)
def trace(sheet, addr, depth, seen):
    key = (sheet, addr)
    if key in seen or depth > 60:
        return
    seen.add(key)
    f = get_formula(sheet, addr)
    if not f:
        return  # лист — вход (константа/значение)
    for rsheet, raddr in refs_in(f):
        if rsheet is None:
            rsheet = sheet
        if rsheet not in all_sheets:
            continue
        trace(rsheet, raddr, depth + 1, seen)


print("=" * 80)
print("ГРАФ ЗАВИСИМОСТЕЙ 10 ПОДСТРАТЕГИЙ")
print("=" * 80)

for idx, (sheet, h, d, a) in enumerate(STRAT_SOURCES):
    name = SUB_NAMES[idx]
    print(f"\n### Подстратегия {idx} [{name}]  ← {sheet}!H{h.split(chr(67))[0] if False else h}")
    # исходные формулы
    hf = get_formula(sheet, h)
    df = get_formula(sheet, d)
    af = get_formula(sheet, a)
    print(f"  home  {h}: {hf}")
    print(f"  draw  {d}: {df}")
    print(f"  away  {a}: {af}")

    # собираем листья отдельно по каждой ячейке
    for label, addr in (("home", h), ("draw", d), ("away", a)):
        seen = set()
        trace(sheet, addr, 0, seen)
        # листья = ячейки с формулой None
        leaves = []
        for (s, ad) in seen:
            if get_formula(s, ad) is None:
                leaves.append(f"{s}!{ad}")
        print(f"  [{label}] листьев-входов: {len(leaves)}")
        # показать первые 25 листьев (сгруппировать)
        by_sheet = {}
        for lv in leaves:
            s = lv.split("!")[0]
            by_sheet.setdefault(s, []).append(lv)
        for s in list(by_sheet)[:12]:
            print(f"      {s}: {len(by_sheet[s])} входов {', '.join(by_sheet[s][:8])}")
