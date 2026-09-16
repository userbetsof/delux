# -*- coding: utf-8 -*-
"""Re-import Module1 (+ optional Module2) into DeluX_IncoProrok_mvp0.xlsm."""
from pathlib import Path

from excel_com import connect_excel

ROOT = Path(r"c:\papki\work\bets\delux")
XLSM = ROOT / "DeluX_IncoProrok_mvp0.xlsm"
MODULES = {
    "Module1": ROOT / "Module1_extracted.bas",
    "Module2": ROOT / "Module2_extracted.bas",
}

REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u00ab": '"',
    "\u00bb": '"',
    "\u201c": '"',
    "\u201d": '"',
}


def to_cp1251(src: Path, name: str) -> Path:
    text = src.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    out = ROOT / f"{name}_cp1251.bas"
    out.write_bytes(text.encode("cp1251", errors="replace"))
    return out


def main() -> None:
    xl = connect_excel(fresh=True)
    try:
        xl.Visible = False
    except Exception:
        pass
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(str(XLSM))
    try:
        vbproj = wb.VBProject
        for module_name, src in MODULES.items():
            for comp in list(vbproj.VBComponents):
                if comp.Name == module_name:
                    vbproj.VBComponents.Remove(comp)
                    break
            bas = to_cp1251(src, module_name)
            vbproj.VBComponents.Import(str(bas))
            print(f"{module_name} re-imported")
        wb.Save()
    finally:
        wb.Close(SaveChanges=True)
        xl.Quit()
    print("Done")


if __name__ == "__main__":
    main()
