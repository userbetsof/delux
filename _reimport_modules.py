# -*- coding: utf-8 -*-
"""Re-import VBA modules into xlsm using Windows-1251 encoding."""
from pathlib import Path
import win32com.client

MODULES = {
    "Module3": Path(r"c:\papki\work\bets\delux\Module3_extracted.bas"),
    "Module5": Path(r"c:\papki\work\bets\delux\Module5_extracted.bas"),
}
OUT_DIR = Path(r"c:\papki\work\bets\delux")
XLSM = Path(r"c:\papki\work\bets\delux\DeluX_IncoProrok_mvp.xlsm")

REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u00ab": '"',
    "\u00bb": '"',
    "\u201c": '"',
    "\u201d": '"',
}


def to_cp1251_bas(src: Path, module_name: str) -> Path:
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
    vbproj = wb.VBProject
    for module_name in MODULES:
        for comp in list(vbproj.VBComponents):
            if comp.Name == module_name:
                vbproj.VBComponents.Remove(comp)
                break
        bas_path = to_cp1251_bas(MODULES[module_name], module_name)
        vbproj.VBComponents.Import(str(bas_path))
        print(f"{module_name} re-imported")
    wb.Save()
finally:
    wb.Close(SaveChanges=True)
    xl.Quit()

print("Done")
