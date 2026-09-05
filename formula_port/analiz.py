"""Порт листа «Анализ» — сборка extract_results()."""

from __future__ import annotations

from typing import Any, Dict, List

from formula_port.cell_store import CellStore
from formula_port.excel_functions import SUBSTITUTE
from formula_port.formula_evaluator import Evaluator, topological_sort
from formula_port.raschety import read_raschety_outputs
from sheets_config import SHEET_ANALYSIS, SHEET_CALC, SHEET_START


def _safe_float(val) -> float:
    try:
        if val is None or val == "":
            return 0.0
        if isinstance(val, int) and val < 0:
            return 0.0
        if isinstance(val, str):
            s = val.strip()
            if not s or s.upper() == "RISK" or s.startswith("#"):
                return 0.0
            return float(s.replace(",", "."))
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _first_number(*vals) -> float:
    for v in vals:
        if v is None or v == "":
            continue
        if isinstance(v, str):
            s = v.strip()
            if not s or s.upper() == "RISK" or s.startswith("#"):
                continue
        return _safe_float(v)
    return 0.0


def _col_letter(n: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(n)


def evaluate_analiz(store: CellStore) -> None:
    ev = Evaluator(store, SHEET_ANALYSIS)
    order = topological_sort(store, [SHEET_ANALYSIS])
    for sheet, addr in order:
        ev.eval_cell(sheet, addr)


def prediction_ntb(store: CellStore, sport: int) -> str:
    z112 = store.get(SHEET_CALC, "Z112")
    if z112 is None:
        z112 = read_raschety_outputs(store).get("Z112", "")
    val = str(z112 or "")
    if sport == 6:
        val = SUBSTITUTE(val, "1X", "\u041f1")
        val = SUBSTITUTE(val, "X2", "\u041f2")
    return val


def extract_results(store: CellStore, sport: int = 1, *, skip_eval: bool = False) -> Dict[str, Any]:
    sport = int(sport or 1)
    if not skip_eval:
        evaluate_analiz(store)

    outcome_probs: List[Dict] = []
    for strategy_idx in range(10):
        row = 8 + strategy_idx * 2
        home = _first_number(store.get(SHEET_ANALYSIS, f"H{row}"), store.get(SHEET_ANALYSIS, f"I{row}"))
        draw = _first_number(store.get(SHEET_ANALYSIS, f"J{row}"), store.get(SHEET_ANALYSIS, f"J{row + 1}"))
        away = _first_number(store.get(SHEET_ANALYSIS, f"K{row}"), store.get(SHEET_ANALYSIS, f"L{row}"))
        outcome_probs.append(
            {
                "strategy_idx": strategy_idx,
                "home_prob": home,
                "draw_prob": draw,
                "away_prob": away,
            }
        )

    home_goals = []
    for col in [22, 23, 24, 25, 26, 27]:
        letter = _col_letter(col)
        home_goals.append(
            _first_number(
                store.get(SHEET_ANALYSIS, f"{letter}10"),
                store.get(SHEET_ANALYSIS, f"{letter}11"),
            )
        )

    away_goals = []
    for col in [35, 36, 37, 38, 39, 40]:
        letter = _col_letter(col)
        away_goals.append(
            _first_number(
                store.get(SHEET_ANALYSIS, f"{letter}10"),
                store.get(SHEET_ANALYSIS, f"{letter}11"),
            )
        )
    ntb = store.get(SHEET_ANALYSIS, "S13")
    if ntb in (None, ""):
        ntb = prediction_ntb(store, sport)

    return {
        "match_date": store.get(SHEET_ANALYSIS, "K2") or "",
        "league": store.get(SHEET_ANALYSIS, "E2") or "",
        "home": store.get(SHEET_ANALYSIS, "E3") or "",
        "away": store.get(SHEET_ANALYSIS, "K3") or "",
        "prediction_ntb": ntb or "",
        "prediction_betalone": store.get(SHEET_ANALYSIS, "O10") or "",
        "prediction_sniper": store.get(SHEET_ANALYSIS, "X24") or "",
        "outcome_probabilities": outcome_probs,
        "home_goals": home_goals,
        "away_goals": away_goals,
    }
