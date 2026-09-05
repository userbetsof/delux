import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN
import formula_port.formula_evaluator as fe

_orig = Evaluator._call_fn


def _call_fn(self, name, args):
    if name in ("IF", "AND", "OR"):
        print(f"CALL {name} n={len(args)} args={args!r}")
    return _orig(self, name, args)


Evaluator._call_fn = _call_fn

forms = load_sheet_formulas(DeluxSettings.from_env().resolve_calc_workbook(), list(DYNAMIC_SHEETS))
x24 = forms[AN]["X24"]
s = CellStore()
s.set_value(AN, "V16", 0.4965)
s.set_value(AN, "X16", 0.1294)
s.set_value(AN, "Z16", 0.3741)
s.set_value(AN, "AE24", 7.5)
s.set_value(AN, "V19", "Х П2")
s.set_formula(AN, "X24", x24)
print("FINAL", repr(Evaluator(s, AN).eval_cell(AN, "X24")))
