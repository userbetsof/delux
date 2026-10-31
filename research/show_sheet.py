"""Показать формулы листа построчно (формула + вычисленное значение).

    py -3 research/show_sheet.py "Расчеты" --from-row 1 --to-row 20
    py -3 research/show_sheet.py "Расчеты" --grep "5Match"
"""

import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

XLSM = Path(r"C:\papki\work\bets\delux\backups\DeluX_IncoProrok_new.xlsm")

# аргументы
sheet_arg = sys.argv[1] if len(sys.argv) > 1 else "Расчеты"
grep = ""
from_row = 0
to_row = 999999
if "--grep" in sys.argv:
    grep = sys.argv[sys.argv.index("--grep") + 1]
if "--from-row" in sys.argv:
    from_row = int(sys.argv[sys.argv.index("--from-row") + 1])
if "--to-row" in sys.argv:
    to_row = int(sys.argv[sys.argv.index("--to-row") + 1])

with zipfile.ZipFile(XLSM) as z:
    # имя листа -> файл
    wb = z.read("xl/workbook.xml").decode("utf-8", errors="replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", errors="replace")

    rel_map = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    sheets = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb)
    target = None
    for name, rid in sheets:
        if name.lower() == sheet_arg.lower():
            tgt = rel_map.get(rid, "")
            target = "xl/" + tgt.lstrip("/").replace("xl/", "", 1)
            print(f"лист: {name} -> {target}")
            break
    if target is None:
        print(f"лист {sheet_arg!r} не найден. Есть:")
        for name, _ in sheets:
            print(f"  {name}")
        raise SystemExit(1)

    # общие строки
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
        for si in re.findall(r"<si>(.*?)</si>", ss, re.S):
            texts = re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)
            shared.append("".join(texts))

    data = z.read(target).decode("utf-8", errors="replace")

    def col_num(ref):
        letters = re.match(r"([A-Z]+)", ref)
        if not letters:
            return 0
        n = 0
        for ch in letters.group(1):
            n = n * 26 + (ord(ch) - 64)
        return n

    printed = 0
    for cell in re.finditer(
        r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', data, re.S
    ):
        ref, attrs, body = cell.group(1), cell.group(2), cell.group(3)
        row = int(re.search(r"(\d+)", ref).group(1))
        if not (from_row <= row <= to_row):
            continue

        f = re.search(r"<f[^>]*>(.*?)</f>", body, re.S)
        v = re.search(r"<v>(.*?)</v>", body, re.S)
        is_str = 't="s"' in attrs

        value = ""
        if v:
            raw = v.group(1)
            if is_str:
                try:
                    value = shared[int(raw)]
                except (ValueError, IndexError):
                    value = raw
            else:
                value = raw

        formula = f.group(1) if f else ""
        if grep and grep.lower() not in formula.lower() and grep.lower() not in str(value).lower():
            continue
        if not formula and not value:
            continue

        print(f"  {ref:6} | {formula[:110]:110} | {str(value)[:40]}")
        printed += 1
        if printed >= 4000:
            print("  … обрезано")
            break

    if not printed:
        print("  (ничего не найдено)")
