"""PythonCalcEngine — расчёт формул (hybrid COM sync или pure_eval без Excel)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analysis_data import AnalysisPayload
from formula_port.analiz import extract_results
from formula_port.cell_store import CellStore
from formula_port.com_guard import reset_com_calls
from formula_port.formula_evaluator import Evaluator, topological_sort
from formula_port.match_context import apply_metadata_overrides, sync_match_context
from formula_port.static_cache import StaticCache
from formula_port.team_stats import (
    apply_odds_to_store,
    apply_payload_to_store,
    apply_queued_odds,
    apply_settings_to_store,
)
from formula_port.incodata_mc import apply_incodata_goal_probs
from formula_port.workbook_loader import load_sheet_constants, load_sheet_formulas
from odds_service import OddsSheetData
from sheets_config import DYNAMIC_SHEETS, SHEET_CALC


def evaluate_dynamic_sheets(store: CellStore, sheets: Optional[List[str]] = None) -> None:
    from sheets_config import SHEET_ANALYSIS

    sheet_list = list(sheets or DYNAMIC_SHEETS)
    ev = Evaluator(store, SHEET_CALC)
    order = topological_sort(store, sheet_list)
    for sheet, addr in order:
        ev.eval_cell(sheet, addr)

    # После ДомаДома/ГостиГости!L/M — MC вместо 50k RAND на IncoData
    apply_incodata_goal_probs(store)
    for addr in (
        "V10",
        "W10",
        "X10",
        "Y10",
        "Z10",
        "AA10",
        "AI10",
        "AJ10",
        "AK10",
        "AL10",
        "AM10",
        "AN10",
        "AE24",
        "X24",
    ):
        key = store.key(SHEET_ANALYSIS, addr)
        store._values.pop(key, None)
        if store.get_formula(SHEET_ANALYSIS, addr):
            ev.eval_cell(SHEET_ANALYSIS, addr)


class PythonCalcEngine:
    """CellStore + формульный движок (hybrid: COM sync или pure eval)."""

    def __init__(
        self,
        workbook_path: str,
        lookups_db: Optional[str] = None,
        *,
        pure_eval: bool = False,
    ):
        self.workbook_path = str(Path(workbook_path).resolve())
        self.static_cache = StaticCache(lookups_db)
        self._formula_cache: Optional[Dict[str, Dict[str, str]]] = None
        self._constants_cache: Optional[Dict[str, Dict[str, object]]] = None
        self.pure_eval = pure_eval

    def _load_formulas(self) -> Dict[str, Dict[str, str]]:
        if self._formula_cache is None:
            self._formula_cache = load_sheet_formulas(self.workbook_path, list(DYNAMIC_SHEETS))
        return self._formula_cache

    def _load_constants(self) -> Dict[str, Dict[str, object]]:
        if self._constants_cache is None:
            sheets = list(self._load_formulas().keys())
            self._constants_cache = load_sheet_constants(self.workbook_path, sheets)
        return self._constants_cache

    def _build_store(
        self,
        payload: AnalysisPayload,
        odds: OddsSheetData,
        list_odds: Optional[Tuple[float, float, float]] = None,
    ) -> CellStore:
        store = CellStore()
        for sheet, mapping in self._load_formulas().items():
            store.bulk_set_formulas(sheet, mapping)

        for sheet, mapping in self._load_constants().items():
            store.bulk_set_values(sheet, mapping)

        if self.static_cache.exists():
            for key, val in self.static_cache.load_all().items():
                if key not in store._formulas and key not in store._values:
                    store._values[key] = val

        apply_payload_to_store(store, payload)
        apply_settings_to_store(store, payload.settings.sport, payload.settings.source)
        apply_odds_to_store(store, odds)
        apply_queued_odds(store, list_odds)

        if self.pure_eval:
            reset_com_calls()
            apply_metadata_overrides(store, payload)
            return store

        sync_match_context(store, self.workbook_path, payload, odds, list_odds)
        apply_metadata_overrides(store, payload)

        for sheet in DYNAMIC_SHEETS:
            for key in list(store._formulas.keys()):
                if key.startswith(f"{sheet}!"):
                    store._formulas.pop(key, None)

        return store

    def run(
        self,
        payload: AnalysisPayload,
        odds: OddsSheetData,
        *,
        list_odds: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        store = self._build_store(payload, odds, list_odds)
        if self.pure_eval:
            evaluate_dynamic_sheets(store)
            results = extract_results(store, sport=payload.settings.sport, skip_eval=True)
        else:
            results = extract_results(store, sport=payload.settings.sport, skip_eval=True)
        results["match_id"] = payload.match.match_id
        results["sport"] = payload.settings.sport
        return results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
