"""Инвентарь Excel-функций в кэше формул vs FUNCTIONS."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from formula_port.excel_functions import FUNCTIONS  # noqa: E402


def main() -> int:
    cache = ROOT / "data" / "formulas_cache.json"
    if not cache.exists():
        print("[-] Missing formulas_cache.json — run build_formula_cache.py")
        return 1
    data = json.loads(cache.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for mapping in data.get("sheets", {}).values():
        for formula in mapping.values():
            for m in re.finditer(r"([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_.]*)\s*\(", formula):
                counts[m.group(1).upper()] += 1

    known = set(FUNCTIONS)
    known |= {k.replace("_XLFN.", "") for k in known}
    missing = sorted(n for n in counts if n not in known and not n.startswith("#"))
    print(f"[+] Unique function-like tokens: {len(counts)}")
    print(f"[+] Implemented: {len(known)}")
    print(f"[+] Missing: {len(missing)}")
    for name in missing[:50]:
        print(f"    {name}: {counts[name]}")
    return 0 if not missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
