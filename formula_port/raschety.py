"""Порт листа «Расчеты» — вычисление Z112 и связанных ячеек."""

from __future__ import annotations

from typing import Any, Dict

from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator, topological_sort
from sheets_config import SHEET_CALC


def evaluate_raschety(store: CellStore) -> None:
    """Пересчитывает все формулы листа Расчеты."""
    ev = Evaluator(store, SHEET_CALC)
    order = topological_sort(store, [SHEET_CALC])
    for sheet, addr in order:
        ev.eval_cell(sheet, addr)


def read_raschety_outputs(store: CellStore) -> Dict[str, Any]:
    return {
        "U112": store.get(SHEET_CALC, "U112"),
        "U114": store.get(SHEET_CALC, "U114"),
        "X112": store.get(SHEET_CALC, "X112"),
        "Y112": store.get(SHEET_CALC, "Y112"),
        "Z112": store.get(SHEET_CALC, "Z112"),
        "X116": store.get(SHEET_CALC, "X116"),
        "Z116": store.get(SHEET_CALC, "Z116"),
    }
