# -*- coding: utf-8 -*-
"""Move AA2 write before getMS(True) in Workbook_Open (getMS quits Excel).

Patches the already-open workbook when possible (avoids ReadOnly).
"""
from excel_com import connect_excel, resolve_workbook_path, _find_open_workbook

XLSM = resolve_workbook_path(r"c:\papki\work\bets\delux\DeluX_IncoProrok_mvp.xlsm")


def _is_aa2_assign(line: str) -> bool:
    s = line.strip()
    return (
        'Range("AA2")' in s
        and "=" in s
        and "IsDate" not in s
        and "CDate" not in s
    )


def _find_open_code(wb):
    for i in range(1, wb.VBProject.VBComponents.Count + 1):
        comp = wb.VBProject.VBComponents(i)
        if comp.Type != 100 or not comp.CodeModule.CountOfLines:
            continue
        text = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
        if "Workbook_Open" in text:
            return comp.CodeModule, comp.Name
    return None, None


def main() -> None:
    # Prefer running Excel so we edit the same file the user has open.
    xl = connect_excel(fresh=False)
    wb = _find_open_workbook(xl, XLSM)
    opened_here = False
    if wb is None:
        xl = connect_excel(fresh=True)
        xl.Visible = False
        xl.DisplayAlerts = False
        xl.EnableEvents = False
        wb = xl.Workbooks.Open(XLSM)
        opened_here = True

    print("ReadOnly", wb.ReadOnly, "opened_here", opened_here)
    if wb.ReadOnly:
        raise SystemExit(
            "Workbook is ReadOnly (close other Excel copy or unlock file), cannot patch."
        )

    try:
        cm, name = _find_open_code(wb)
        if cm is None:
            raise SystemExit("Workbook_Open not found")
        print("found", repr(name), "lines", cm.CountOfLines)

        getms_line = None
        aa2_assigns = []
        for n in range(1, cm.CountOfLines + 1):
            line = cm.Lines(n, 1)
            if "Call getMS(True)" in line:
                getms_line = n
            if _is_aa2_assign(line):
                aa2_assigns.append(n)

        print("getms_line", getms_line, "aa2_assigns", aa2_assigns)
        if getms_line is None:
            raise SystemExit("Call getMS(True) not found")

        already_ok = aa2_assigns and aa2_assigns[0] < getms_line and len(aa2_assigns) == 1
        if already_ok:
            # Ensure Save is present before getMS
            prev = cm.Lines(getms_line - 1, 1) if getms_line > 1 else ""
            if "ThisWorkbook.Save" not in prev:
                cm.InsertLines(getms_line, "        ThisWorkbook.Save\r\n")
                print("Inserted ThisWorkbook.Save")
            else:
                print("Already fixed")
        else:
            # Rebuild the critical tail of the If block cleanly
            # Find "If lastRunDate" block start and End If / End Sub
            if_line = end_if_line = None
            for n in range(1, cm.CountOfLines + 1):
                line = cm.Lines(n, 1).strip()
                if line.startswith("If lastRunDate"):
                    if_line = n
                if if_line and line == "End If":
                    end_if_line = n
                    break
            if not if_line or not end_if_line:
                raise SystemExit("If lastRunDate block not found")

            # Keep lines from start through V2=8, then inject AA2+Save+getMS
            # Find V2 = 8 line
            v2_line = None
            for n in range(if_line, end_if_line):
                if 'Range("V2")' in cm.Lines(n, 1) and "8" in cm.Lines(n, 1):
                    v2_line = n
            if v2_line is None:
                raise SystemExit("V2=8 line not found")

            # Delete everything after v2_line until End If (exclusive)
            delete_start = v2_line + 1
            delete_count = end_if_line - delete_start
            if delete_count > 0:
                cm.DeleteLines(delete_start, delete_count)

            block = (
                '        wsStart.Range("AA2").value = currentDate\r\n'
                "        ThisWorkbook.Save\r\n"
                "        Call getMS(True) 'true\r\n"
            )
            cm.InsertLines(v2_line + 1, block)
            print("Rebuilt block after V2=8")

        wb.Save()
        print("==== AFTER ====")
        for n in range(1, cm.CountOfLines + 1):
            print(f"{n}|{cm.Lines(n, 1)}")
    finally:
        if opened_here:
            wb.Close(SaveChanges=True)
            xl.Quit()
    print("Done")


if __name__ == "__main__":
    main()
