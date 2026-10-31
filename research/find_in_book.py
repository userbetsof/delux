import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

XLSM = Path(r"C:\papki\work\bets\delux\backups\DeluX_IncoProrok_new.xlsm")
PATTERN = sys.argv[1] if len(sys.argv) > 1 else "5Match"

with zipfile.ZipFile(XLSM) as z:
    names = z.namelist()
    wb = z.read("xl/workbook.xml").decode("utf-8", errors="replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", errors="replace")
    rel_map = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    sheet_map = {}
    for name, rid in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        tgt = rel_map.get(rid, "")
        sheet_map["xl/" + tgt.lstrip("/").replace("xl/", "", 1)] = name

    shared = []
    if "xl/sharedStrings.xml" in names:
        ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
        for si in re.findall(r"<si>(.*?)</si>", ss, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))

    print(f"ищем {PATTERN!r} в строках и формулах:\n")
    hits = 0
    for path, sheet in sorted(sheet_map.items()):
        if not path.endswith(".xml"):
            continue
        try:
            data = z.read(path).decode("utf-8", errors="replace")
        except KeyError:
            continue
        for cell in re.finditer(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', data, re.S):
            ref, attrs, body = cell.groups()
            f = re.search(r"<f[^>]*>(.*?)</f>", body, re.S)
            v = re.search(r"<v>(.*?)</v>", body, re.S)
            formula = f.group(1) if f else ""
            value = ""
            if v:
                raw = v.group(1)
                if 't="s"' in attrs:
                    try:
                        value = shared[int(raw)]
                    except (ValueError, IndexError):
                        value = raw
                else:
                    value = raw
            blob = f"{formula} {value}"
            if PATTERN.lower() in blob.lower():
                print(f"[{sheet}] {ref}")
                if formula:
                    print(f"   формула: {formula[:300]}")
                if value:
                    print(f"   значение: {value[:120]}")
                hits += 1
                if hits >= 60:
                    print("\n… обрезано (60)")
                    raise SystemExit(0)
    if not hits:
        print("не найдено")
