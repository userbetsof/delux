"""Запись листов «Таблица» и «Форма» в открытый .xlsm (с склейкой MLB AL+NL)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_data import build_settings, fetch_table  # noqa: E402
from excel_com import (  # noqa: E402
    connect_excel,
    open_workbook,
    restore_excel_ui,
    snapshot_excel_ui,
)
from sheets_config import SHEET_FORM, SHEET_START, SHEET_TABLE  # noqa: E402


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _write_block(ws, start_col: int, start_row: int, rows: list) -> None:
    if not rows:
        return
    end_row = start_row + len(rows) - 1
    end_col = start_col + len(rows[0]) - 1
    addr = f"{_col_letter(start_col)}{start_row}:{_col_letter(end_col)}{end_row}"
    ws.Range(addr).Value = rows


def _table_matrix(rows) -> list:
    return [
        [r.rank, r.team, r.played, r.wins, r.draws, r.losses, r.scored, r.conceded, r.points]
        for r in rows
    ]


def _headers() -> list[str]:
    return [
        "Место",
        "Команда",
        "Игр",
        "Выиграно",
        "Ничьих",
        "Проиграно",
        "Забито",
        "Пропущено",
        "Очков",
    ]


def fill_tables(workbook: str, match_id: str, sport: int | None = None) -> int:
    # Вызывается из VBA getGame при уже открытой книге — НЕ трогаем Visible,
    # иначе Excel «исчезает» и после анализа не возвращается.
    xl = connect_excel()
    ui_state = snapshot_excel_ui(xl)
    try:
        if ui_state.get("Visible", True):
            xl.Visible = True
        wb = open_workbook(xl, workbook)
        ws_start = wb.Worksheets(SHEET_START)
        if sport is None:
            try:
                sport = int(float(ws_start.Range("R2").Value or 1))
            except (TypeError, ValueError):
                sport = 1
        try:
            source = int(float(ws_start.Range("X2").Value or 2))
        except (TypeError, ValueError):
            source = 2
        try:
            tz_base = int(float(ws_start.Range("T2").Value or 16))
        except (TypeError, ValueError):
            tz_base = 16
        try:
            time_offset = int(float(ws_start.Range("AA3").Value or 10))
        except (TypeError, ValueError):
            time_offset = 10

        ms = build_settings(
            sport=sport,
            source=source,
            tz_base=tz_base,
            time_offset=time_offset,
        )

        ws_table = wb.Worksheets(SHEET_TABLE)
        ws_form = wb.Worksheets(SHEET_FORM)
        ws_table.Columns("A:AC").ClearContents()
        ws_form.Columns("A:AC").ClearContents()
        for start_col in (1, 11, 21):
            for offset, title in enumerate(_headers()):
                ws_table.Cells(1, start_col + offset).Value = title
                ws_form.Cells(1, start_col + offset).Value = title

        blocks = (
            ("table_overall", 1, ws_table),
            ("table_home", 11, ws_table),
            ("table_away", 21, ws_table),
            ("form_overall", 1, ws_form),
            ("form_home", 11, ws_form),
            ("form_away", 21, ws_form),
        )
        for name, col, ws in blocks:
            rows = fetch_table(ms, match_id, name)
            data = _table_matrix(rows)
            _write_block(ws, col, 2, data)
            print(f"[+] {name}: {len(rows)} rows (unique {len({r.team for r in rows})})")

        # Не закрываем книгу — VBA продолжает getGame в том же Excel.
        return 0
    finally:
        restore_excel_ui(xl, ui_state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--sport", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(fill_tables(args.workbook, args.match_id, args.sport))


if __name__ == "__main__":
    main()
