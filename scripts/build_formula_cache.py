"""Сборка кэша формул: только ячейки, достижимые от выходов Анализ."""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from formula_port.refs import parse_formula_refs  # noqa: E402
from settings import DeluxSettings  # noqa: E402
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS  # noqa: E402

OUTPUT_CELLS = [
    (SHEET_ANALYSIS, "S13"),
    (SHEET_ANALYSIS, "O10"),
    (SHEET_ANALYSIS, "X24"),
    (SHEET_ANALYSIS, "E2"),
    (SHEET_ANALYSIS, "K2"),
    (SHEET_ANALYSIS, "E3"),
    (SHEET_ANALYSIS, "K3"),
]
for idx in range(10):
    row = 8 + idx * 2
    for col in ("H", "I", "J", "K", "L"):
        OUTPUT_CELLS.append((SHEET_ANALYSIS, f"{col}{row}"))
    OUTPUT_CELLS.append((SHEET_ANALYSIS, f"J{row + 1}"))
for col_n in list(range(22, 28)) + list(range(35, 41)):
    from openpyxl.utils import get_column_letter

    letter = get_column_letter(col_n)
    OUTPUT_CELLS.append((SHEET_ANALYSIS, f"{letter}10"))
    OUTPUT_CELLS.append((SHEET_ANALYSIS, f"{letter}11"))


def load_all_formulas(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    store: dict = {}
    for name in wb.sheetnames:
        ws = wb[name]
        sheet_formulas = {}
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if val is not None and str(val).startswith("="):
                    sheet_formulas[cell.coordinate] = str(val)
        if sheet_formulas:
            store[name] = sheet_formulas
    wb.close()
    return store


# Листы с огромным числом RAND/NORM.INV — только BFS от выходов, не полный дамп.
_FULL_DUMP_SKIP = frozenset({"IncoData"})


def reachable_formulas(all_formulas: dict) -> dict:
    """Полный снимок DYNAMIC_SHEETS (кроме IncoData) + BFS для остального."""
    wanted_sheets = set(DYNAMIC_SHEETS)
    out: dict = {s: {} for s in wanted_sheets}

    for sheet in wanted_sheets:
        if sheet in _FULL_DUMP_SKIP:
            continue
        if sheet in all_formulas:
            out[sheet] = dict(all_formulas[sheet])

    queue: deque = deque(OUTPUT_CELLS)
    seen = set()
    while queue:
        sheet, addr = queue.popleft()
        key = f"{sheet}!{addr}"
        if key in seen:
            continue
        seen.add(key)
        formula = all_formulas.get(sheet, {}).get(addr)
        if not formula:
            continue
        if sheet in wanted_sheets:
            out.setdefault(sheet, {})[addr] = formula
        for ref in parse_formula_refs(formula, default_sheet=sheet):
            queue.append((ref.sheet, ref.a1()))
            if ref.sheet not in wanted_sheets and ref.sheet in all_formulas:
                f2 = all_formulas[ref.sheet].get(ref.a1())
                if f2:
                    out.setdefault(ref.sheet, {})[ref.a1()] = f2
    return {k: v for k, v in out.items() if v}


def main():
    cfg = DeluxSettings.from_env()
    workbook = cfg.resolve_calc_workbook()
    print("[*] Loading workbook formulas...")
    all_f = load_all_formulas(workbook)
    print(f"    sheets with formulas: {len(all_f)}")
    print("[*] BFS from Analysis outputs...")
    formulas = reachable_formulas(all_f)
    out = ROOT / "data" / "formulas_cache.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"workbook": workbook, "sheets": formulas}, f, ensure_ascii=False)
    total = sum(len(v) for v in formulas.values())
    print(f"[+] Cached {total} reachable formulas -> {out}")
    for name, mapping in sorted(formulas.items(), key=lambda x: -len(x[1])):
        print(f"    {name}: {len(mapping)}")


if __name__ == "__main__":
    main()
