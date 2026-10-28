"""Debug formula loading in PythonCalcEngine."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas
from sheets_config import DYNAMIC_SHEETS

formulas = load_sheet_formulas("", list(DYNAMIC_SHEETS))

print(f"Loaded formulas for {len(formulas)} sheets:")
for sheet, mapping in formulas.items():
    print(f"  {sheet}: {len(mapping)} formulas")
    if 'Incognito DATA' in sheet:
        for addr, formula in sorted(mapping.items()):
            if 'B2' in addr or 'C2' in addr or 'D2' in addr or 'G16' in addr:
                print(f"    {addr}: {formula[:100]}")
