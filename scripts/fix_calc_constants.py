"""Прописывает константы листа «Расчеты» (Poisson-сетка, блоки «Дома»/«Гости»/«Ничья»)
в data/lookups.db и data/formulas_cache.json.

Причина: в кэшах отсутствовали AZ5:AZ12, BC5:BC12, BD/BE/BJ/BK/BP/BQ — то есть вся
Poisson-сетка «Расчеты!AZ5:BB12». VLOOKUP(BF5/AZ5:BB12) давал 0 → BH/BN = 0 →
BA17 (X116) и BA19 (Z116) оба 0 → Расчеты!Z112 пустой → NTB (#1) не считался ни
для одного матча.

Значения взяты из реального delux_incoprorok_mvp.xlsm (строки 5..12, плюс
зеркальный блок 13..32, где счётчики сдвинуты, чтобы покрыть BH5:BH32 и BN5:BN32).

    py -3 scripts\\fix_calc_constants.py           # записать
    py -3 scripts\\fix_calc_constants.py --check   # только проверить
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "formulas_cache.json"
LOOKUPS = ROOT / "data" / "lookups.db"
SHEET = "Расчеты"


def build_constants() -> dict:
    """Константы «Расчеты» по данным эталонного .xlsm."""
    consts: dict[str, object] = {}

    # Poisson-сетка голов 0..7 (AZ — голы хозяев, BB — голы гостей)
    for i, row in enumerate(range(5, 13)):
        consts[f"AZ{row}"] = i
        consts[f"BC{row}"] = i
        # Блок «Ничья»: BP=BQ=счёт (диагональ сетки)
        consts[f"BP{row}"] = i
        consts[f"BQ{row}"] = i

    # «Дома» (BD=Г1/BJ=К2) и «Гости» (BE=Г2/BK=К1)
    home_block = [7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4]
    away_block = [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 0, 1, 2, 3]
    for offset, row in enumerate(range(5, 33)):
        consts[f"BD{row}"] = home_block[offset]
        consts[f"BE{row}"] = away_block[offset]
        consts[f"BJ{row}"] = away_block[offset]
        consts[f"BK{row}"] = home_block[offset]

    return consts


def patch_formulas_cache(consts: dict, *, check: bool) -> None:
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    sheet = data["sheets"].setdefault(SHEET, {})
    missing = [k for k in consts if k not in sheet]
    print(f"  formulas_cache.json: добавить {len(missing)}")
    if check or not missing:
        return
    shutil.copy2(CACHE, CACHE.with_suffix(".json.bak"))
    sheet.update(consts)
    CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"  formulas_cache.json: записано (бэкап .json.bak)")


def patch_lookups(consts: dict, *, check: bool) -> None:
    if not LOOKUPS.is_file():
        print("  lookups.db: нет файла, пропуск")
        return
    conn = sqlite3.connect(LOOKUPS)
    try:
        existing = {
            row[0]
            for row in conn.execute(
                "SELECT cell FROM lookup_values WHERE sheet = ?", (SHEET,)
            ).fetchall()
        }
        missing = [k for k in consts if k not in existing]
        print(f"  lookups.db: добавить {len(missing)}")
        if check or not missing:
            return
        shutil.copy2(LOOKUPS, LOOKUPS.with_suffix(".db.bak"))
        conn.executemany(
            "INSERT OR REPLACE INTO lookup_values "
            "(cell_key, sheet, cell, value_text, value_num, value_type) "
            "VALUES (?, ?, ?, NULL, ?, 'float')",
            [(f"{SHEET}!{k}", SHEET, k, float(consts[k])) for k in missing],
        )
        conn.commit()
        print("  lookups.db: записано (бэкап .db.bak)")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    consts = build_constants()
    print(f"констант «{SHEET}»: {len(consts)}")
    patch_formulas_cache(consts, check=args.check)
    patch_lookups(consts, check=args.check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
