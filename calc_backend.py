"""Фабрика calc-движков. По умолчанию Python без Excel."""

from __future__ import annotations

from typing import Union

from formula_port.engine import PythonCalcEngine
from formula_port.workbook_loader import has_formula_cache
from settings import DeluxSettings

CalcEngine = Union["ExcelCalcEngine", PythonCalcEngine]


def _optional_workbook(cfg: DeluxSettings) -> str:
    try:
        return cfg.resolve_calc_workbook()
    except FileNotFoundError:
        return ""


def get_calc_engine(cfg: DeluxSettings | None = None) -> CalcEngine:
    cfg = cfg or DeluxSettings.from_env()
    if cfg.calc_backend != "python":
        workbook = cfg.resolve_calc_workbook()
        from calc_engine import ExcelCalcEngine

        return ExcelCalcEngine(workbook)

    if has_formula_cache():
        return PythonCalcEngine("", pure_eval=True)

    workbook = _optional_workbook(cfg)
    if not workbook:
        raise FileNotFoundError(
            "Нет data/formulas_cache.json и нет .xlsm. "
            "Для расчёта нужен кэш формул (без Excel)."
        )
    return PythonCalcEngine(workbook, pure_eval=True)
