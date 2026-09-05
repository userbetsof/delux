import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import formula_port.excel_functions as ef
from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN

_orig = ef.IF


def _IF(cond, true_val=False, false_val=False, *rest):
    result = _orig(cond, true_val, false_val)
    print(
        f"IF cond={cond!r} ({type(cond).__name__}) "
        f"T={true_val!r} F={false_val!r} rest={rest} -> {result!r}"
    )
    return result


ef.IF = _IF
ef.FUNCTIONS["IF"] = _IF

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
