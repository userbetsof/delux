"""Порт листа «Графики» — M30:M32, BD39 и промежуточные ячейки."""

from __future__ import annotations

from typing import Any, Dict

from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator, topological_sort
from sheets_config import SHEET_GRAFIKI


def evaluate_grafiki(store: CellStore) -> None:
    ev = Evaluator(store, SHEET_GRAFIKI)
    order = topological_sort(store, [SHEET_GRAFIKI])
    for sheet, addr in order:
        ev.eval_cell(sheet, addr)


def read_grafiki_outputs(store: CellStore) -> Dict[str, Any]:
    return {
        "M26": store.get(SHEET_GRAFIKI, "M26"),
        "M27": store.get(SHEET_GRAFIKI, "M27"),
        "M28": store.get(SHEET_GRAFIKI, "M28"),
        "M30": store.get(SHEET_GRAFIKI, "M30"),
        "M31": store.get(SHEET_GRAFIKI, "M31"),
        "M32": store.get(SHEET_GRAFIKI, "M32"),
        "BD39": store.get(SHEET_GRAFIKI, "BD39"),
    }
