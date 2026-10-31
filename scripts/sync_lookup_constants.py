"""Синхронизировать константы из книги в data/lookups.db.

Движок (formula_port/engine.py) берёт статические значения из двух мест:
  1. formulas_cache.json  — формулы
  2. lookups.db           — константы (StaticCache)

Константы, которые есть только в книге (Таблица, Очные, Графики AK/AL),
в lookups.db отсутствовали. Из-за этого VLOOKUP(P24,Таблица!...) получал
пустоту → #N/A → стратегия mill показывала 0%.

    py -3 scripts/sync_lookup_constants.py --dry-run
    py -3 scripts/sync_lookup_constants.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from add_missing_constants import (  # noqa: E402
    load_shared_strings,
    read_constants,
    sheet_files,
)

LOOKUPS = ROOT / "data" / "lookups.db"
XLSM = ROOT / "backups" / "DeluX_IncoProrok_new.xlsm"

# листы, где лежат нужные стратегиям константы
SHEETS = ("Графики", "Таблица", "Очные", "ОчныеДГ", "Форма", "Анализ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--xlsm", default=str(XLSM))
    args = parser.parse_args()

    if not Path(args.xlsm).is_file():
        print(f"[-] нет книги: {args.xlsm}")
        return 1

    conn = sqlite3.connect(str(LOOKUPS))
    existing = {
        r[0] for r in conn.execute("SELECT cell_key FROM lookup_values").fetchall()
    }
    print(f"в lookups.db сейчас: {len(existing)} значений")

    added = 0
    with zipfile.ZipFile(args.xlsm) as z:
        shared = load_shared_strings(z)
        files = sheet_files(z)
        for sheet in SHEETS:
            path = files.get(sheet)
            if not path:
                continue
            constants = read_constants(z, path, shared)
            rows = []
            for ref, val in constants.items():
                key = f"{sheet}!{ref}"
                if key in existing:
                    continue
                if isinstance(val, str):
                    rows.append((key, sheet, ref, val, None, "str"))
                elif isinstance(val, float):
                    rows.append((key, sheet, ref, None, val, "float"))
                else:
                    rows.append((key, sheet, ref, str(val), None, "str"))
            if rows:
                print(f"  {sheet}: +{len(rows)}")
                added += len(rows)
                if not args.dry_run:
                    conn.executemany(
                        "INSERT OR REPLACE INTO lookup_values "
                        "(cell_key, sheet, cell, value_text, value_num, value_type) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        rows,
                    )

    print()
    print(f"добавлено: {added}")
    if args.dry_run:
        print("[dry-run] база не изменена")
    else:
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM lookup_values").fetchone()[0]
        print(f"в lookups.db стало: {total}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
