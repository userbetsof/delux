import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN

forms = load_sheet_formulas(DeluxSettings.from_env().resolve_calc_workbook(), list(DYNAMIC_SHEETS))
x24 = forms[AN]["X24"]
Path(__file__).with_name("_x24_formula.txt").write_text(x24, encoding="utf-8")
print("len", len(x24), "parens", x24.count("("), x24.count(")"))
print("ends with", repr(x24[-80:]))
