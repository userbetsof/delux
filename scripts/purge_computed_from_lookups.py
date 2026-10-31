"""Удалить из lookups.db значения ячеек, которые должны вычисляться формулой.

Проблема: в lookups.db накопились результаты прошлых расчётов (из другого
матча) для ячеек, у которых в книге ЕСТЬ формула. Например:
    Mill!P24 = 'Сан-Франциско Джайентс'  (из бейсбольного матча)
    Mill!R27 = 523.0
    Mill!S49 = 311.0
Движок подставляет их как константы, формула не считается, и mill
показывает 0.

Правило: если ячейка есть в formulas_cache.json как «=...», её значение
из lookups.db надо убрать — пусть считается заново.

    py -3 scripts/purge_computed_from_lookups.py --dry-run
    py -3 scripts/purge_computed_from_lookups.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

CACHE = ROOT / "data" / "formulas_cache.json"
LOOKUPS = ROOT / "data" / "lookups.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.load(CACHE.open(encoding="utf-8"))
    formulas = data.get("sheets", {})

    # cell_key -> True для всех формульных ячеек
    formula_keys: set[str] = set()
    for sheet, mapping in formulas.items():
        for addr, val in mapping.items():
            if isinstance(val, str) and val.startswith("="):
                formula_keys.add(f"{sheet}!{addr}")

    conn = sqlite3.connect(str(LOOKUPS))
    rows = conn.execute("SELECT cell_key FROM lookup_values").fetchall()
    present = {r[0] for r in rows}

    to_delete = sorted(formula_keys & present)
    print(f"формульных ячеек в кэше: {len(formula_keys)}")
    print(f"из них есть в lookups.db: {len(to_delete)}")

    from collections import Counter
    import re

    by_sheet = Counter(re.match(r"([^!]+)!", k).group(1) for k in to_delete)
    print("по листам:", dict(by_sheet.most_common(10)))
    print()
    print("примеры:", to_delete[:8])

    if args.dry_run:
        print()
        print("[dry-run] база не изменена")
        return 0
    if not to_delete:
        print("нечего удалять")
        return 0

    cur = conn.executemany(
        "DELETE FROM lookup_values WHERE cell_key = ?",
        [(k,) for k in to_delete],
    )
    conn.commit()
    print()
    print(f"удалено: {cur.rowcount}")
    total = conn.execute("SELECT COUNT(*) FROM lookup_values").fetchone()[0]
    print(f"в lookups.db осталось: {total}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
