"""Minimal repro: Дома!J/N and Графики!O IF string compare."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from formula_port.cell_store import CellStore
from formula_port.formula_evaluator import Evaluator, _tokenize
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS

wb = DeluxSettings.from_env().resolve_calc_workbook()
forms = load_sheet_formulas(wb, list(DYNAMIC_SHEETS))
home = "Дома"
graf = "Графики"

print("J2", forms.get(home, {}).get("J2"))
print("N2", forms.get(home, {}).get("N2"))
print("O2", forms.get(graf, {}).get("O2"))
print("tok O2", _tokenize(forms[graf]["O2"]))

s = CellStore()
s.bulk_set_formulas(home, forms[home])
s.set_value(home, "I2", "Гости")
s.set_value(home, "E2", 1)
s.set_value(home, "F2", 0)
s.set_value(home, "G2", 0)
s.set_value(home, "H2", 0)
ev = Evaluator(s, home)
print("eval J2", repr(ev.eval_cell(home, "J2")))
print("eval N2", repr(ev.eval_cell(home, "N2")))
print("has formula J2", s.get_formula(home, "J2"))
print("E2", s.get(home, "E2"), "I2", s.get(home, "I2"))

s2 = CellStore()
s2.set_formula("T", "A1", '=IF(B1="Дома",1,0)')
s2.set_value("T", "B1", "Гости")
print("IF Гости", Evaluator(s2, "T").eval_cell("T", "A1"))
s3 = CellStore()
s3.set_formula("T", "A1", '=IF(B1="Дома",1,0)')
s3.set_value("T", "B1", "Дома")
print("IF Дома", Evaluator(s3, "T").eval_cell("T", "A1"))

s4 = CellStore()
s4.set_value(graf, "M2", "Гости")
s4.set_value(graf, "L2", "")
s4.set_formula(graf, "O2", forms[graf]["O2"])
print("O2 when M=Гости L=''", Evaluator(s4, graf).eval_cell(graf, "O2"))

# empty L2 == "В" ?
s5 = CellStore()
s5.set_formula("T", "A1", '=IF(B1="В",1,0)')
s5.set_value("T", "B1", "")
print('IF ""=="В"', Evaluator(s5, "T").eval_cell("T", "A1"))
s6 = CellStore()
s6.set_formula("T", "A1", '=B1="В"')
s6.set_value("T", "B1", "")
print('cmp ""="В"', Evaluator(s6, "T").eval_cell("T", "A1"))
# empty cell as 0 vs "В"
from formula_port.formula_evaluator import Evaluator as Ev

s7 = CellStore()
s7.set_formula("T", "A1", '=IF(B1="Дома",IF(C1="В",1,0),0)')
s7.set_value("T", "B1", "Гости")
# C1 missing -> 0
print("nested IF Гости missing C", Ev(s7, "T").eval_cell("T", "A1"))
s7.set_value("T", "B1", "Дома")
print("nested IF Дома missing C", Ev(s7, "T").eval_cell("T", "A1"))
