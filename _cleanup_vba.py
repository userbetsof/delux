# -*- coding: utf-8 -*-
"""Remove duplicate VBA modules and re-import Module3/Module5."""
from pathlib import Path
import re
import win32com.client

XLSM = Path(r"c:\papki\work\bets\delux\DeluX_IncoProrok_mvp.xlsm")
OUT_DIR = Path(r"c:\papki\work\bets\delux")
MODULES = {
    "Module3": OUT_DIR / "Module3_extracted.bas",
    "Module5": OUT_DIR / "Module5_extracted.bas",
}
KEEP = {
    "Module1", "Module2", "Module3", "Module4", "Module5", "Module6",
    "mCustomProgressBarModule",
}
REPLACEMENTS = {
    "\u2014": "-", "\u2013": "-", "\u00ab": '"', "\u00bb": '"',
    "\u201c": '"', "\u201d": '"',
}
OLD_BEST = re.compile(r'best\s*=\s*""\s*Or\s*CDbl')


def to_cp1251(src: Path, module_name: str) -> Path:
    text = src.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    out = OUT_DIR / f"{module_name}_cp1251.bas"
    out.write_bytes(text.encode("cp1251"))
    return out


xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
wb = xl.Workbooks.Open(str(XLSM))
try:
    vb = wb.VBProject
    # Remove duplicate modules (Module31, Module51, Module52, etc.)
    for comp in list(vb.VBComponents):
        if comp.Type != 1:
            continue
        name = comp.Name
        if name not in KEEP:
            print(f"Removing duplicate: {name}")
            vb.VBComponents.Remove(comp)

    for module_name, src in MODULES.items():
        for comp in list(vb.VBComponents):
            if comp.Name == module_name:
                vb.VBComponents.Remove(comp)
                break
        bas_path = to_cp1251(src, module_name)
        vb.VBComponents.Import(str(bas_path))
        print(f"{module_name} re-imported")

    # Verify Module5 only (FindMaxMarketOdds lives there)
    cm = vb.VBComponents("Module5").CodeModule
    n = cm.CountOfLines
    code = cm.Lines(1, n) if n > 0 else ""
    if OLD_BEST.search(code):
        raise RuntimeError("Module5 still has old best= line")
    if "Not IsNumeric(best)" not in code:
        raise RuntimeError("Module5 missing IsNumeric(best) fix")
    print(f"Module5: OK ({n} lines)")

    wb.Save()
    print("Done")
finally:
    wb.Close(SaveChanges=True)
    xl.Quit()
