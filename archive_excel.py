"""Порт VBA ТоАрхив / TransferKfData / FindMatchingCombination → Excel sheets."""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from odds_coeff import (
    ODDS_BK_COLS,
    ODDS_DATA_START_ROW,
    ODDS_FIRST_BK_COL,
    calc_prediction_value,
    find_max_market_odds,
    get_last_col,
    get_last_row,
)
from sheets_config import SHEET_ANALYSIS, SHEET_CALC, SHEET_ODDS, SHEET_START

SHEET_ARCHIVE = "achive"
SHEET_SUB_STRATEGIES = "sub_strategies"
SHEET_KF = "kf"


def _safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _is_error(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and (val.startswith("#") or val.upper() == "RISK"):
        return True
    return False


def _to_float(val) -> float:
    try:
        if val is None or val == "":
            return 0.0
        if isinstance(val, str):
            s = val.strip().replace(",", ".")
            if not s or s.startswith("#"):
                return 0.0
            return float(s)
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _archive_has_match(ws_archive, match_id: str) -> bool:
    last = ws_archive.Cells(ws_archive.Rows.Count, "A").End(-4162).Row
    for row in range(1, last + 1):
        if _safe_str(ws_archive.Range(f"A{row}").Value) == match_id:
            return True
    return False


def _next_archive_row(ws_archive) -> int:
    last = ws_archive.Cells(ws_archive.Rows.Count, "C").End(-4162).Row
    return max(last + 1, 2)


def transfer_kf_data(wb) -> None:
    """Порт VBA TransferKfData: max CURRENT odds по рынкам → лист kf."""
    ws_old = wb.Worksheets(SHEET_ODDS)
    try:
        ws_new = wb.Worksheets(SHEET_KF)
    except Exception:
        return

    last_col = get_last_col(ws_old)
    if last_col < ODDS_FIRST_BK_COL:
        return
    last_row = get_last_row(ws_old, last_col)

    markets: dict[str, Tuple[Optional[float], Optional[float]]] = {}
    start_col = ODDS_FIRST_BK_COL
    while start_col <= last_col:
        for r in range(ODDS_DATA_START_ROW, last_row + 1):
            market_name = _safe_str(ws_old.Cells(r, start_col).Value)
            if not market_name:
                break
            open_val = ws_old.Cells(r, start_col + 1).Value
            cur_val = ws_old.Cells(r, start_col + 2).Value
            open_f = _to_float(open_val) if open_val not in (None, "") else None
            cur_f = _to_float(cur_val) if cur_val not in (None, "") else None
            if open_f is None and cur_f is None:
                continue
            if open_f == 0.0 and cur_f == 0.0 and not isinstance(open_val, (int, float)) and not isinstance(cur_val, (int, float)):
                continue
            prev_open, prev_cur = markets.get(market_name, (None, None))
            if open_f is not None and open_f > 0 and (prev_open is None or open_f > prev_open):
                prev_open = open_f
            if cur_f is not None and cur_f > 0 and (prev_cur is None or cur_f > prev_cur):
                prev_cur = cur_f
            markets[market_name] = (prev_open, prev_cur)
        start_col += ODDS_BK_COLS

    if not markets:
        return

    if not _safe_str(ws_new.Cells(1, 1).Value):
        ws_new.Cells(1, 1).Value = "MATCH_ID"
    if not _safe_str(ws_new.Cells(1, 2).Value):
        ws_new.Cells(1, 2).Value = "HOME_ID"
    if not _safe_str(ws_new.Cells(1, 3).Value):
        ws_new.Cells(1, 3).Value = "AWAY_ID"

    header_last = ws_new.Cells(1, ws_new.Columns.Count).End(-4159).Column
    name_to_col: dict[str, int] = {}
    for col in range(1, header_last + 1):
        name = _safe_str(ws_new.Cells(1, col).Value)
        if name:
            name_to_col[name] = col

    for market_name in markets:
        if market_name not in name_to_col:
            header_last = ws_new.Cells(1, ws_new.Columns.Count).End(-4159).Column + 1
            ws_new.Cells(1, header_last).Value = market_name
            name_to_col[market_name] = header_last

    last_row_new = ws_new.Cells(ws_new.Rows.Count, 1).End(-4162).Row
    if last_row_new == 1 and not _safe_str(ws_new.Cells(1, 1).Value):
        last_row_new = 0
    dest_row = max(last_row_new + 1, 2)

    match_id = wb.Worksheets(SHEET_CALC).Range("A1").Value
    ws_new.Cells(dest_row, 1).Value = match_id
    ws_new.Cells(dest_row, 2).Value = ws_old.Range("A2").Value
    ws_new.Cells(dest_row, 3).Value = ws_old.Range("B2").Value

    for market_name, (_o, cur) in markets.items():
        col = name_to_col.get(market_name)
        if not col or cur is None:
            continue
        try:
            ws_new.Cells(dest_row, int(col)).Value = float(cur)
        except Exception:
            try:
                ws_new.Cells(dest_row, int(col)).Value = cur
            except Exception as exc:
                print(f"[!] kf write {market_name} col={col}: {exc}")

    try:
        ws_new.Rows(1).Font.Bold = True
    except Exception:
        pass


def find_matching_combination(wb) -> Tuple[Any, Any]:
    """Упрощённый порт VBA FindMatchingCombination → (номер или Empty, tip)."""
    ws_an = wb.Worksheets(SHEET_ANALYSIS)
    ws_odds = wb.Worksheets(SHEET_ODDS)

    kf_p1 = _to_float(ws_an.Range("B11").Value)
    kf_tb25 = find_max_market_odds(ws_odds, "OVER 2.5", "CURRENT")
    kf_oz = find_max_market_odds(ws_odds, "BTTS_YES", "CURRENT")
    kf_itb1 = find_max_market_odds(ws_odds, "ИТБ1 (2.5)", "CURRENT")
    if kf_itb1 <= 0:
        kf_itb1 = find_max_market_odds(ws_odds, "HOME OVER 2.5", "CURRENT")
    kf_f2 = find_max_market_odds(ws_odds, "HANDICAP AWAY -1.5", "CURRENT")
    kf_itb2 = find_max_market_odds(ws_odds, "ИТБ2 (2.5)", "CURRENT")
    if kf_itb2 <= 0:
        kf_itb2 = find_max_market_odds(ws_odds, "AWAY OVER 2.5", "CURRENT")
    kf_tb15_1h = find_max_market_odds(ws_odds, "OVER 1.5 1st Half", "CURRENT")
    if kf_tb15_1h <= 0:
        kf_tb15_1h = find_max_market_odds(ws_odds, "1st Half OVER 1.5", "CURRENT")

    # 1: П1 ≤ 1.20 + ТБ 2.5 ≤ 1.45
    if 0 < kf_p1 <= 1.2 and 0 < kf_tb25 <= 1.45:
        return 1, "ТБ 4.5"
    # 2: ТБ2.5 + ИТБ1 + ОЗ
    if 0 < kf_tb25 <= 1.45 and 0 < kf_itb1 <= 1.6 and 0 < kf_oz <= 1.55:
        return 2, "ТБ 3.5"
    # 3: Ф2 + ИТБ2 + ТБ2.5
    if 0 < kf_f2 <= 1.5 and 0 < kf_itb2 <= 1.55 and 0 < kf_tb25 <= 1.5:
        return 3, "ТБ 4.5 или ИТБ2 3.5"
    # 4: ОЗ + ТБ2.5 + ТБ 1Т
    if 0 < kf_oz <= 1.45 and 0 < kf_tb25 <= 1.55 and 0 < kf_tb15_1h <= 1.85:
        return 4, "ТБ 3.5"
    return None, None


def find_closest_under2_over(wb) -> Tuple[Any, Any]:
    """Порт FindClosestUnder2Over: OVER half-line с кэфом < 2, ближайший к 2."""
    ws = wb.Worksheets(SHEET_ODDS)
    last_col = get_last_col(ws)
    if last_col < ODDS_FIRST_BK_COL:
        return None, None
    last_row = get_last_row(ws, last_col)

    best_market = ""
    min_diff = 1000.0
    half_skip = ("1st Half", "2nd Half", " Half", "1st", "2nd", "Half", "тайм", "Half Time")

    start_col = ODDS_FIRST_BK_COL
    while start_col <= last_col:
        for r in range(ODDS_DATA_START_ROW, last_row + 1):
            header = _safe_str(ws.Cells(r, start_col).Value)
            if not header:
                break
            if "OVER" not in header.upper() and "OVER" not in header:
                continue
            if any(tok.lower() in header.lower() for tok in half_skip if tok.strip()):
                # VBA skips period totals; keep full-time only
                if any(tok in header for tok in ("1st Half", "2nd Half", "Half Time", "тайм")):
                    continue
                if re.search(r"\b(1st|2nd)\b", header) and "Half" in header:
                    continue
            m = re.search(r"(\d+[.,]\d+|\d+)", header.replace("OVER", ""))
            if not m:
                continue
            try:
                total_number = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            # half-totals only (x.5)
            if abs(total_number * 2 - round(total_number * 2)) > 1e-9:
                continue
            if int(total_number * 2) % 2 == 0:
                continue
            cell_value = _to_float(ws.Cells(r, start_col + 2).Value)
            if 0 < cell_value < 2.0:
                diff = 2.0 - cell_value
                if not best_market or diff < min_diff:
                    min_diff = diff
                    best_market = header
        start_col += ODDS_BK_COLS

    if not best_market:
        return None, None
    odds = find_max_market_odds(ws, best_market, "CURRENT")
    return odds if odds > 0 else None, best_market


def write_sub_strategies(wb, row: int) -> None:
    ws_an = wb.Worksheets(SHEET_ANALYSIS)
    try:
        ws_sub = wb.Worksheets(SHEET_SUB_STRATEGIES)
    except Exception:
        return

    mapping = [
        ("A", "H12"),
        ("B", "J12"),
        ("C", "K12"),
        ("D", "H8"),
        ("E", "J8"),
        ("F", "K8"),
        ("G", "H10"),
        ("H", "J10"),
        ("I", "K10"),
        ("J", "H14"),
        ("K", "J14"),
        ("L", "K14"),
        ("M", "H16"),
        ("N", "J16"),
        ("O", "K16"),
        ("P", "H18"),
        ("Q", "J18"),
        ("R", "K18"),
        ("S", "H20"),
        ("T", "J20"),
        ("U", "K20"),
        ("V", "H22"),
        ("W", "J22"),
        ("X", "K22"),
        ("Y", "H24"),
        ("Z", "J24"),
        ("AA", "K24"),
        ("AB", "H26"),
        ("AC", "J26"),
        ("AD", "K26"),
    ]
    for col, addr in mapping:
        ws_sub.Range(f"{col}{row}").Value = ws_an.Range(addr).Value


def write_archive_coefficients(wb, row: int) -> None:
    ws_an = wb.Worksheets(SHEET_ANALYSIS)
    ws_odds = wb.Worksheets(SHEET_ODDS)
    ws_archive = wb.Worksheets(SHEET_ARCHIVE)

    ntb = calc_prediction_value(ws_an.Range("S13").Value, ws_odds)
    sniper = calc_prediction_value(ws_an.Range("X24").Value, ws_odds)
    betalone = calc_prediction_value(ws_an.Range("O10").Value, ws_odds)
    ws_archive.Range(f"L{row}").Value = ntb if ntb is not None else ""
    ws_archive.Range(f"T{row}").Value = sniper if sniper is not None else ""
    ws_archive.Range(f"P{row}").Value = betalone if betalone is not None else ""


def archive_match(wb, *, save: bool = True, update_existing: bool = True) -> Optional[int]:
    """
    Порт ТоАрхив (без запуска db.py — вызывающий решает про БД).
    Возвращает номер строки архива или None если skip (ошибка S13).
    """
    ws_an = wb.Worksheets(SHEET_ANALYSIS)
    ws_calc = wb.Worksheets(SHEET_CALC)
    ws_archive = wb.Worksheets(SHEET_ARCHIVE)
    ws_start = wb.Worksheets(SHEET_START)

    ntb = ws_an.Range("S13").Value
    if _is_error(ntb):
        print("[!] Архив: S13 ошибка — пропуск")
        return None

    match_id = _safe_str(ws_calc.Range("A1").Value)
    if not match_id:
        print("[!] Архив: пустой Расчеты!A1")
        return None

    existing_row = None
    last = ws_archive.Cells(ws_archive.Rows.Count, "A").End(-4162).Row
    for row in range(1, last + 1):
        if _safe_str(ws_archive.Range(f"A{row}").Value) == match_id:
            existing_row = row
            break

    if existing_row is not None and not update_existing:
        print(f"[*] Архив: {match_id} уже есть — пропуск")
        return None

    q1 = existing_row if existing_row is not None else _next_archive_row(ws_archive)
    if existing_row is not None:
        print(f"[*] Архив: обновление строки {q1} для {match_id}")
    else:
        print(f"[+] Архив: новая строка {q1} для {match_id}")

    ws_archive.Range(f"A{q1}").Value = match_id
    ws_archive.Range(f"B{q1}").Value = ws_start.Range("R2").Value
    ws_archive.Range(f"C{q1}").Value = ws_an.Range("K2").Value
    ws_archive.Range(f"D{q1}").Value = ws_an.Range("E2").Value
    ws_archive.Range(f"E{q1}").Value = ws_an.Range("E3").Value
    ws_archive.Range(f"F{q1}").Value = ws_an.Range("K3").Value
    ws_archive.Range(f"K{q1}").Value = ntb
    ws_archive.Range(f"O{q1}").Value = ws_an.Range("O10").Value

    write_archive_coefficients(wb, q1)
    ws_archive.Range(f"S{q1}").Value = ws_an.Range("X24").Value

    combo_num, _combo_tip = find_matching_combination(wb)
    if combo_num is not None:
        ws_archive.Range(f"W{q1}").Value = combo_num
    else:
        ws_archive.Range(f"W{q1}").Value = ""

    write_sub_strategies(wb, q1)

    if combo_num is not None:
        odds_val, market = find_closest_under2_over(wb)
        if odds_val is not None and market:
            total_value = (
                str(market)
                .replace("OVER", "")
                .replace("1st Half", "")
                .strip()
            )
            m = re.search(r"(\d+[.,]\d+|\d+)", total_value)
            tip = m.group(1).replace(".", ",") if m else total_value
            ws_archive.Range(f"W{q1}").Value = f"ТБ {tip}"
            ws_archive.Range(f"X{q1}").Value = odds_val

    try:
        transfer_kf_data(wb)
    except Exception as exc:
        print(f"[!] TransferKfData: {exc}")

    if save:
        try:
            wb.Save()
        except Exception as exc:
            print(f"[!] Save workbook: {exc}")

    return q1
