import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import formula_port.excel_functions as ef
from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator, _tokenize
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN

_orig_and = ef.AND


def _AND(*args):
    print("AND args", args)
    return _orig_and(*args)


ef.AND = _AND
ef.FUNCTIONS["AND"] = _AND

# tokenize the AND fragments
f = '=AND(X16>=39%,X16<=48%)'
print("tok", _tokenize(f))
f2 = '=AND(Z16>=45%,Z16<=55%,X16<=38%)'
print("tok2", _tokenize(f2))

forms = load_sheet_formulas(DeluxSettings.from_env().resolve_calc_workbook(), list(DYNAMIC_SHEETS))
x24 = forms[AN]["X24"]
s = CellStore()
s.set_value(AN, "V16", 0.4965)
s.set_value(AN, "X16", 0.1294)
s.set_value(AN, "Z16", 0.3741)
s.set_value(AN, "AE24", 7.5)
s.set_value(AN, "V19", "Х П2")
s.set_formula(AN, "X24", x24)
print("result", repr(Evaluator(s, AN).eval_cell(AN, "X24")))
