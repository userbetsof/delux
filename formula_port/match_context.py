"""Синхронизация match-dependent ячеек из Excel в CellStore."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Set, Tuple

from analysis_data import AnalysisPayload
from formula_port.cell_store import CellStore
from formula_port.com_guard import note_com_call
from odds_service import OddsSheetData
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS, SHEET_CALC, SHEET_GRAFIKI

ROOT = Path(__file__).resolve().parent.parent
PYTHON_EVAL_SHEETS = set(DYNAMIC_SHEETS)


def _load_graph_nodes() -> dict:
    graph_path = ROOT / "data" / "formula_graph.json"
    if not graph_path.exists():
        return {}
    with open(graph_path, encoding="utf-8") as f:
        return json.load(f).get("nodes", {})


def _sync_range(store: CellStore, wb, sheet: str, start: str, end: str) -> int:
    from formula_port.refs import col_row
    from openpyxl.utils import get_column_letter

    try:
        ws = wb.Worksheets(sheet)
        block = ws.Range(f"{start}:{end}").Value
    except Exception:
        return 0
    if block is None:
        return 0
    sc, sr = col_row(start)
    if not isinstance(block, tuple):
        block = ((block,),)
    written = 0
    for ri, row in enumerate(block):
        if not isinstance(row, tuple):
            row = (row,)
        for ci, val in enumerate(row):
            addr = f"{get_column_letter(sc + ci)}{sr + ri}"
            store.set_value(sheet, addr, val)
            store._formulas.pop(store.key(sheet, addr), None)
            written += 1
    return written


def sync_match_context(
    store: CellStore,
    workbook_path: str,
    payload: AnalysisPayload,
    odds: OddsSheetData,
    list_odds: Optional[Tuple[float, float, float]] = None,
) -> int:
    """Excel: payload + calc → значения всех ячеек графа кроме Расчеты/Графики/Анализ."""
    from calc_engine import ExcelCalcEngine

    note_com_call()
    nodes = _load_graph_nodes()
    with ExcelCalcEngine(workbook_path) as eng:
        eng.write_payload(payload)
        if list_odds:
            eng.write_list_odds_1x2(*list_odds)
        eng.write_odds(odds)
        eng.calculate()
        wb = eng.wb

        written = 0
        for key, node in nodes.items():
            sheet = node.get("sheet", "")
            addr = node.get("cell", "")
            if not sheet or not addr or sheet in PYTHON_EVAL_SHEETS:
                continue
            try:
                val = wb.Worksheets(sheet).Range(addr).Value
            except Exception:
                continue
            store.set_value(sheet, addr, val)
            store._formulas.pop(store.key(sheet, addr), None)
            written += 1

        written += _sync_range(store, wb, "Таблица", "A1", "Z35")
        written += _sync_range(store, wb, "Коэффициенты", "A1", "Z50")
        written += _sync_range(store, wb, SHEET_CALC, "A1", "BZ120")
        written += _sync_range(store, wb, SHEET_GRAFIKI, "A1", "BM70")
        written += _sync_range(store, wb, SHEET_ANALYSIS, "A1", "AN30")
    return written


def apply_metadata_overrides(store: CellStore, payload: AnalysisPayload) -> None:
    """Метаданные матча — прямые значения (без формул Incognito DATA)."""
    match = payload.match
    for addr in ("E2", "K2", "E3", "K3"):
        store._formulas.pop(store.key(SHEET_ANALYSIS, addr), None)
    if match.league:
        store.set_value(SHEET_ANALYSIS, "E2", match.league)
    if match.date:
        store.set_value(SHEET_ANALYSIS, "K2", match.date)
    if match.home:
        store.set_value(SHEET_ANALYSIS, "E3", match.home)
    if match.away:
        store.set_value(SHEET_ANALYSIS, "K3", match.away)
