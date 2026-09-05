"""Загрузка формул из .xlsm или кэша в CellStore."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

import openpyxl

from formula_port.cell_store import CellStore

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "formulas_cache.json"


def load_sheet_formulas_from_workbook(
    workbook_path: str, wanted: set
) -> Dict[str, Dict[str, str]]:
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    out: Dict[str, Dict[str, str]] = {}
    for name in wb.sheetnames:
        if name not in wanted:
            continue
        ws = wb[name]
        formulas = {}
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if val is not None and str(val).startswith("="):
                    formulas[cell.coordinate] = str(val)
        out[name] = formulas
    wb.close()
    return out


def load_sheet_formulas(workbook_path: str, sheet_names: Iterable[str]) -> Dict[str, Dict[str, str]]:
    wanted = set(sheet_names)
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        sheets = cached.get("sheets", {})
        # Use cache even if it is a reachable subset of requested sheets
        if sheets:
            return {k: v for k, v in sheets.items() if (not wanted or k in wanted)}
    return load_sheet_formulas_from_workbook(workbook_path, wanted)


def load_sheet_constants(
    workbook_path: str, sheet_names: Iterable[str]
) -> Dict[str, Dict[str, object]]:
    """Неформульные значения на листах (стартовые константы)."""
    wanted = set(sheet_names)
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    out: Dict[str, Dict[str, object]] = {}
    for name in wb.sheetnames:
        if name not in wanted:
            continue
        ws = wb[name]
        values = {}
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if val is None:
                    continue
                if isinstance(val, str) and val.startswith("="):
                    continue
                values[cell.coordinate] = val
        out[name] = values
    wb.close()
    return out


def populate_formula_store(workbook_path: str, sheet_names: List[str]) -> CellStore:
    store = CellStore()
    formulas = load_sheet_formulas(workbook_path, sheet_names)
    for sheet, mapping in formulas.items():
        store.bulk_set_formulas(sheet, mapping)
    return store
