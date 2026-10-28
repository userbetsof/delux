"""PythonCalcEngine — расчёт формул (hybrid COM sync или pure_eval без Excel)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analysis_data import AnalysisPayload
from formula_port.analiz import extract_results
from formula_port.cell_store import CellStore
from formula_port.com_guard import reset_com_calls
from formula_port.formula_evaluator import Evaluator, topological_sort
from formula_port.match_context import apply_metadata_overrides
from formula_port.static_cache import StaticCache
from formula_port.team_stats import (
    apply_odds_to_store,
    apply_payload_to_store,
    apply_queued_odds,
    apply_settings_to_store,
)
from formula_port.incodata_mc import apply_incodata_goal_probs, strip_goal_hist_formulas
from formula_port.workbook_loader import load_sheet_constants, load_sheet_formulas
from odds_service import OddsSheetData
from sheets_config import DYNAMIC_SHEETS, SHEET_CALC


def _clear_formula_values(store: CellStore, sheets: List[str]) -> None:
    """Сбросить кэш значений у формул, чтобы eval не брал lookups.db / snapshot."""
    wanted = set(sheets)
    for key in store._formulas:
        sheet = key.split("!", 1)[0]
        if sheet in wanted:
            store._values.pop(key, None)


def _eval_sheet_formulas(store: CellStore, sheets: List[str], ev: Evaluator) -> None:
    for sheet, addr in topological_sort(store, sheets):
        ev.eval_cell(sheet, addr)


def evaluate_dynamic_sheets(store: CellStore, sheets: Optional[List[str]] = None) -> None:
    sheet_list = list(sheets or DYNAMIC_SHEETS)
    # Не считать COUNTIF по 50k RAND: MC подставит гистограмму после L/M.
    strip_goal_hist_formulas(store)
    _clear_formula_values(store, sheet_list)
    ev = Evaluator(store, SHEET_CALC)
    _eval_sheet_formulas(store, sheet_list, ev)

    apply_incodata_goal_probs(store)
    # Poisson / Mill / 1pr и т.д. зависят от пересчитанных голов — второй проход.
    _clear_formula_values(store, sheet_list)
    _eval_sheet_formulas(store, sheet_list, ev)


class PythonCalcEngine:
    """CellStore + формульный движок (hybrid: COM sync или pure eval)."""

    def __init__(
        self,
        workbook_path: str = "",
        lookups_db: Optional[str] = None,
        *,
        pure_eval: bool = True,
    ):
        self.workbook_path = str(Path(workbook_path).resolve()) if workbook_path else ""
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
        # В кэше формул встречаются и неформульные значения (константы листа),
        # поэтому в формулы отдаём только строки, начинающиеся с "=".
        for sheet, mapping in self._load_formulas().items():
            store.bulk_set_formulas(
                sheet,
                {
                    addr: val
                    for addr, val in mapping.items()
                    if isinstance(val, str) and val.startswith("=")
                },
            )

        formula_keys = set(store._formulas)
        # Неформульные значения из кэша формул (если попали туда) — как константы.
        for sheet, mapping in self._load_formulas().items():
            for addr, val in mapping.items():
                key = store.key(sheet, addr)
                if key in formula_keys:
                    continue
                store.set_value(sheet, addr, val)
        for sheet, mapping in self._load_constants().items():
            for addr, val in mapping.items():
                key = store.key(sheet, addr)
                if key in formula_keys:
                    continue
                store.set_value(sheet, addr, val)

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

        if not self.workbook_path:
            raise RuntimeError("hybrid calc requires .xlsm; use FORMULA_PURE_EVAL=true")
        from formula_port.match_context import sync_match_context

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
