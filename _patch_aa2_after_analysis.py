# -*- coding: utf-8 -*-
"""Патч VBA: AA2 только после успешного анализа; Quit только если были матчи.

Симптом: AA2 обновилась → Excel закрылся → анализа не было → повтор сегодня не стартует.
"""
from __future__ import annotations

from pathlib import Path

from excel_com import _find_open_workbook, connect_excel, resolve_workbook_path

ROOT = Path(__file__).resolve().parent
XLSM = resolve_workbook_path(str(ROOT / "DeluX_IncoProrok_mvp.xlsm"))

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
    out = ROOT / f"{module_name}_cp1251.bas"
    out.write_bytes(text.encode("cp1251", errors="replace"))
    return out


def find_thisworkbook(wb):
    for i in range(1, wb.VBProject.VBComponents.Count + 1):
        comp = wb.VBProject.VBComponents(i)
        if comp.Type != 100 or not comp.CodeModule.CountOfLines:
            continue
        text = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
        if "Workbook_Open" in text:
            return comp
    return None


def patch_thisworkbook(cm) -> None:
    """Убрать AA2+Save перед getMS — дату пишет getMS после анализа."""
    getms_line = None
    for n in range(1, cm.CountOfLines + 1):
        if "Call getMS(True)" in cm.Lines(n, 1):
            getms_line = n
            break
    if getms_line is None:
        raise SystemExit("Call getMS(True) not found")

    # Удалить строки AA2= и ThisWorkbook.Save непосредственно перед getMS
    to_delete = []
    for n in range(max(1, getms_line - 5), getms_line):
        line = cm.Lines(n, 1).strip()
        if 'Range("AA2")' in line and "=" in line and "IsDate" not in line:
            to_delete.append(n)
        if "ThisWorkbook.Save" in line or "ActiveWorkbook.Save" in line:
            to_delete.append(n)

    for n in reversed(to_delete):
        print(f"[-] ThisWorkbook delete L{n}: {cm.Lines(n, 1).rstrip()}")
        cm.DeleteLines(n, 1)

    # Комментарий перед getMS (если ещё нет)
    # пересчитать getms_line
    getms_line = None
    for n in range(1, cm.CountOfLines + 1):
        if "Call getMS(True)" in cm.Lines(n, 1):
            getms_line = n
            break
    prev = cm.Lines(getms_line - 1, 1) if getms_line > 1 else ""
    if "AA2" not in prev and "успешн" not in prev.lower() and "getMS" not in prev:
        cm.InsertLines(
            getms_line,
            "        ' AA2 ставит getMS только после реального анализа\r\n",
        )
        print("[+] ThisWorkbook comment inserted")
    print("[+] ThisWorkbook_Open patched")


def reimport_module1(wb) -> None:
    src = ROOT / "Module1_extracted.bas"
    if not src.exists():
        raise SystemExit(f"missing {src}")
    vbproj = wb.VBProject
    for i in range(1, vbproj.VBComponents.Count + 1):
        comp = vbproj.VBComponents(i)
        if comp.Name == "Module1":
            vbproj.VBComponents.Remove(comp)
            print("[-] removed old Module1")
            break
    bas = to_cp1251_bas(src, "Module1")
    vbproj.VBComponents.Import(str(bas))
    print(f"[+] imported Module1 from {bas.name}")


def reset_aa2_to_yesterday(wb) -> None:
    """Чтобы автозапуск снова сработал сегодня после фикса."""
    import datetime as dt

    import pywintypes

    ws = None
    for i in range(1, wb.Sheets.Count + 1):
        sh = wb.Sheets(i)
        name = str(sh.Name)
        if name == "Старт" or "тарт" in name:
            ws = sh
            break
    if ws is None:
        print("[!] sheet Старт not found, skip AA2 reset")
        return
    old = ws.Range("AA2").Value
    yesterday = dt.datetime.combine(dt.date.today() - dt.timedelta(days=1), dt.time())
    ws.Range("AA2").Value = pywintypes.Time(yesterday)
    print(f"[+] AA2 reset: {old!r} -> {ws.Range('AA2').Value!r}")


def main() -> None:
    xl = connect_excel(fresh=True)
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    xl.AskToUpdateLinks = False

    wb = _find_open_workbook(xl, XLSM)
    opened_here = False
    if wb is None:
        wb = xl.Workbooks.Open(str(XLSM))
        opened_here = True
    print("[*] workbook", wb.FullName, "RO", wb.ReadOnly, "opened_here", opened_here)
    if wb.ReadOnly:
        raise SystemExit("ReadOnly — закройте другие копии Excel")

    try:
        tw = find_thisworkbook(wb)
        if tw is None:
            raise SystemExit("Workbook_Open not found")
        print("[*] ThisWorkbook component", repr(tw.Name), "lines", tw.CodeModule.CountOfLines)
        patch_thisworkbook(tw.CodeModule)
        reimport_module1(wb)
        reset_aa2_to_yesterday(wb)
        wb.Save()
        print("[+] saved")

        # verify
        tw2 = find_thisworkbook(wb)
        print("==== ThisWorkbook AFTER ====")
        for n in range(1, tw2.CodeModule.CountOfLines + 1):
            print(f"{n}|{tw2.CodeModule.Lines(n, 1)}")
        m1 = wb.VBProject.VBComponents("Module1")
        print("==== Module1 getMS/autoAnalisis head ====")
        for n in range(1, min(120, m1.CodeModule.CountOfLines) + 1):
            print(f"{n}|{m1.CodeModule.Lines(n, 1)}")
    finally:
        if opened_here:
            wb.Close(SaveChanges=True)
            xl.Quit()
    print("Done")


if __name__ == "__main__":
    main()
