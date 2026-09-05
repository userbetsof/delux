# -*- coding: utf-8 -*-
"""Re-import Module3 into xlsm using Windows-1251 encoding for VBA."""
from pathlib import Path
import win32com.client

SRC = Path(r"c:\papki\work\bets\delux\Module3_extracted.bas")
OUT = Path(r"c:\papki\work\bets\delux\Module3_cp1251.bas")
XLSM = Path(r"c:\papki\work\bets\delux\DeluX_IncoProrok_mvp.xlsm")

text = SRC.read_text(encoding="utf-8")
# VBA on Russian Windows expects CP1251; avoid smart punctuation in comments.
replacements = {
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u00ab": '"',   # «
    "\u00bb": '"',   # »
    "\u201c": '"',
    "\u201d": '"',
}
for old, new in replacements.items():
    text = text.replace(old, new)

OUT.write_bytes(text.encode("cp1251"))

xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
wb = xl.Workbooks.Open(str(XLSM))
try:
    vbproj = wb.VBProject
    for comp in list(vbproj.VBComponents):
        if comp.Name in ("Module3", "Module31"):
            vbproj.VBComponents.Remove(comp)
    vbproj.VBComponents.Import(str(OUT))
    cm = vbproj.VBComponents("Module3").CodeModule
    line7 = cm.Lines(7, 1)
    if "\u0421\u043f\u0438\u0441\u043e\u043a" not in line7:
        raise RuntimeError("Module3 encoding check failed after import")
    if "For Each lineKey In linesDict.Keys" not in cm.Lines(1, cm.CountOfLines):
        raise RuntimeError("ParseTotals fix missing after import")
    wb.Save()
    print("Module3 re-imported with CP1251 encoding")
finally:
    wb.Close(SaveChanges=True)
    xl.Quit()
