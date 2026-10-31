"""Убрать из formulas_cache.json значения, попавшие туда по ошибке.

Файл предназначен только для ФОРМУЛ (строки, начинающиеся с «=»).
Константы (числа и текст вроде «Гавр») должны лежать в data/lookups.db —
их читает StaticCache.

Если константа попала в formulas_cache.json, engine считает её формулой,
пытается вычислить и получает пустое значение. Именно поэтому
Очные!A1 («Гавр») терялось и VLOOKUP в Mill давал #N/A.

    py -3 scripts/purge_constants_from_formulas.py --dry-run
    py -3 scripts/purge_constants_from_formulas.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "formulas_cache.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def is_formula(val: object) -> bool:
    return isinstance(val, str) and val.startswith("=")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.load(CACHE.open(encoding="utf-8"))
    sheets = data.get("sheets", {})

    total = 0
    for sheet, mapping in sheets.items():
        not_formulas = [k for k, v in mapping.items() if not is_formula(v)]
        if not not_formulas:
            continue
        print(f"  {sheet}: -{len(not_formulas)} (например {not_formulas[:3]})")
        total += len(not_formulas)
        if not args.dry_run:
            for key in not_formulas:
                mapping.pop(key, None)

    print()
    print(f"неформульных значений: {total}")
    if args.dry_run:
        print("[dry-run] файл не изменён")
        return 0
    if not total:
        print("нечего удалять")
        return 0

    backup = CACHE.with_suffix(".json.bak4")
    shutil.copy2(CACHE, backup)
    print(f"резервная копия: {backup.name}")
    CACHE.write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("кэш формул очищен от констант")
    return 0


if __name__ == "__main__":
    sys.exit(main())
