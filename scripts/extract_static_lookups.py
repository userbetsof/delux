"""Экспорт статических значений ячеек из .xlsm в data/lookups.db."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from excel_com import connect_excel, open_workbook  # noqa: E402
from formula_port.static_cache import StaticCache  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def parse_cell_key(key: str):
    sheet, addr = key.split("!", 1)
    return sheet, addr


def export_lookups(workbook_path: str, graph_path: Path, db_path: Path) -> int:
    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)

    static_keys = graph.get("static_cells") or []
    if not static_keys:
        static_keys = [
            k for k, v in graph.get("nodes", {}).items() if v.get("sheet_class") == "static"
        ]

    xl = connect_excel()
    xl.Visible = False
    xl.ScreenUpdating = False
    wb = open_workbook(xl, workbook_path)
    xl.CalculateFullRebuild()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE lookup_values (
            cell_key TEXT PRIMARY KEY,
            sheet TEXT NOT NULL,
            cell TEXT NOT NULL,
            value_text TEXT,
            value_num REAL,
            value_type TEXT
        )
        """
    )
    conn.execute(
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute(
        "INSERT INTO meta VALUES ('workbook', ?)",
        (workbook_path,),
    )
    conn.execute(
        "INSERT INTO meta VALUES ('cell_count', ?)",
        (str(len(static_keys)),),
    )

    written = 0
    for key in static_keys:
        sheet, addr = parse_cell_key(key)
        try:
            ws = wb.Worksheets(sheet)
            val = ws.Range(addr).Value
        except Exception:
            continue

        value_text = None
        value_num = None
        value_type = type(val).__name__

        if val is None:
            value_type = "none"
        elif isinstance(val, bool):
            value_text = str(val)
        elif isinstance(val, (int, float)):
            value_num = float(val)
        else:
            value_text = str(val)

        conn.execute(
            """
            INSERT OR REPLACE INTO lookup_values
            (cell_key, sheet, cell, value_text, value_num, value_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key, sheet, addr, value_text, value_num, value_type),
        )
        written += 1

    conn.commit()
    conn.close()
    print(f"[+] Exported {written} static cells -> {db_path}")
    return written


def main():
    cfg = DeluxSettings.from_env()
    workbook = cfg.resolve_calc_workbook()
    graph_path = ROOT / "data" / "formula_graph.json"
    db_path = ROOT / "data" / "lookups.db"
    if not graph_path.exists():
        print("[-] Run trace_dependencies.py first")
        raise SystemExit(1)
    raise SystemExit(0 if export_lookups(workbook, graph_path, db_path) > 0 else 1)


if __name__ == "__main__":
    main()
