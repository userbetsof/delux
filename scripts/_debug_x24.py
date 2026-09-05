import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator, _tokenize
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN

s = CellStore()
s.set_value(AN, "V16", 0.4965)
s.set_value(AN, "X16", 0.1294)
s.set_value(AN, "Z16", 0.3741)
s.set_value(AN, "AE24", 7.5)
s.set_value(AN, "V19", "Х П2")

tests = [
    ("A1", "=X16<25%"),
    ("A2", "=X16>58%"),
    ("A3", '="ТБ "&AE24'),
    ("A4", '=IF(X16<25%,"ТБ "&AE24,"NO")'),
    ("A5", '=IF(V19<>"",V19,"empty")'),
    ("A6", '=IF(V16>Z16,"1X","X2")'),
]
ev = Evaluator(s, AN)
for addr, f in tests:
    s.set_formula(AN, addr, f)
    print(addr, repr(ev.eval_cell(AN, addr)))

forms = load_sheet_formulas(DeluxSettings.from_env().resolve_calc_workbook(), list(DYNAMIC_SHEETS))
x24 = forms[AN]["X24"]
print("X24 len", len(x24))
print(x24[:200])
s2 = CellStore()
s2.set_value(AN, "V16", 0.4965)
s2.set_value(AN, "X16", 0.1294)
s2.set_value(AN, "Z16", 0.3741)
s2.set_value(AN, "AE24", 7.5)
s2.set_value(AN, "V19", "Х П2")
s2.set_formula(AN, "X24", x24)
print("X24 full", repr(Evaluator(s2, AN).eval_cell(AN, "X24")))
