"""Показать структуру листа «Таблица»: все блоки, заголовки, диапазоны."""

import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

XLSM = r"C:\papki\work\bets\delux\backups\DeluX_IncoProrok_new.xlsm"

with zipfile.ZipFile(XLSM) as z:
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
        for si in re.findall(r"<si>(.*?)</si>", ss, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))

    d = z.read("xl/worksheets/sheet22.xml").decode("utf-8", errors="replace")

    # найдём последнюю строку
    dim = re.search(r'<dimension ref="([^"]+)"', d)
    print("диапазон листа:", dim.group(1) if dim else "?")

    rows: dict[int, dict[str, object]] = {}
    for m in re.finditer(
        r'<c r="([A-Z]+)(\d+)"((?:[^>/]|/(?!>))*)>(.*?)</c>', d, re.S
    ):
        col, row_s, attrs, body = m.groups()
        v = re.search(r"<v>(.*?)</v>", body, re.S)
        if not v:
            continue
        raw = v.group(1)
        if 't="s"' in attrs:
            try:
                val: object = shared[int(raw)]
            except (ValueError, IndexError):
                val = raw
        else:
            try:
                val = float(raw)
            except ValueError:
                val = raw
        rows.setdefault(int(row_s), {})[col] = val

    print(f"строк с данными: {len(rows)}")
    print()
    print("Первые 35 строк (все непустые ячейки):")
    for r in sorted(rows)[:35]:
        cells = rows[r]
        parts = []
        for col in sorted(cells, key=lambda c: (len(c), c)):
            v = cells[col]
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            parts.append(f"{col}={v!r}")
        print(f"  стр.{r:3}: " + ", ".join(parts)[:160])
