import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formula_port.formula_evaluator import _tokenize
from formula_port.workbook_loader import load_sheet_formulas
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_ANALYSIS as AN

forms = load_sheet_formulas(DeluxSettings.from_env().resolve_calc_workbook(), list(DYNAMIC_SHEETS))
x24 = forms[AN]["X24"]
toks = _tokenize(x24)
for i, t in enumerate(toks):
    if t[0] == "NAME" and t[1] in ("AND", "IF", "OR", "IFERROR", "VLOOKUP", "COUNTIF"):
        window = toks[i : i + 15]
        print(i, window)
