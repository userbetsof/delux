"""Фабрика calc-движков (Excel COM или Python)."""

from __future__ import annotations

from typing import Union

from formula_port.engine import PythonCalcEngine
from settings import DeluxSettings

# ExcelCalcEngine тянет excel_com; на Linux импортируем только при CALC_BACKEND=excel.
CalcEngine = Union["ExcelCalcEngine", PythonCalcEngine]


def get_calc_engine(cfg: DeluxSettings | None = None) -> CalcEngine:
    cfg = cfg or DeluxSettings.from_env()
    workbook = cfg.resolve_calc_workbook()
    if cfg.calc_backend == "python":
        return PythonCalcEngine(workbook, pure_eval=cfg.formula_pure_eval)
    from calc_engine import ExcelCalcEngine

    return ExcelCalcEngine(workbook)
