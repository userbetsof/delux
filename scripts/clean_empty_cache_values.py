"""Убрать пустые значения из formulas_cache.json.

Проблема: при сборке store константы из кэша формул загружаются ПЕРЕД
StaticCache (lookups.db), а StaticCache пропускает ключи, которые уже
есть в store — даже если там пустая строка. Из-за этого Очные!A1 = ''
перекрывал настоящее значение «Гавр», VLOOKUP давал #N/A и стратегия
mill показывала 0.

Скрипт удаляет из кэша пустые значения (None и ""), чтобы они не мешали
брать данные из lookups.db.

    py -3 scripts/clean_empty_cache_values.py --dry-run
    py -3 scripts/clean_empty_cache_values.py
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


def is_empty(val: object) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.load(CACHE.open(encoding="utf-8"))
    sheets = data.get("sheets", {})

    removed_total = 0
    for sheet, mapping in sheets.items():
        to_remove = [k for k, v in mapping.items() if is_empty(v)]
        if not to_remove:
            continue
        # показываем примеры
        sample = ", ".join(to_remove[:5])
        print(f"  {sheet}: -{len(to_remove)} ({sample}…)")
        removed_total += len(to_remove)
        if not args.dry_run:
            for key in to_remove:
                mapping.pop(key, None)

    print()
    print(f"пустых значений: {removed_total}")
    if args.dry_run:
        print("[dry-run] кэш не изменён")
        return 0
    if not removed_total:
        print("нечего удалять")
        return 0

    backup = CACHE.with_suffix(".json.bak3")
    shutil.copy2(CACHE, backup)
    print(f"резервная копия: {backup.name}")
    CACHE.write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("кэш обновлён")
    return 0


if __name__ == "__main__":
    sys.exit(main())
