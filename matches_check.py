import argparse
import re
from typing import Dict, Tuple

import win32com.client

from excel_com import connect_excel, open_workbook
from flashscore_feed import fetch_feed, iter_feed_rows, map_source, parse_fields
from match_settle import STATUSES


def parse_match_time(time_string: str) -> Tuple[str, str]:
    period = ""
    minute = ""
    ts = (time_string or "").strip()
    if not ts:
        return period, minute
    if ts.lstrip("-").isdigit():
        tv = int(ts)
        if tv < 0:
            return "До матча", ""
        if 0 <= tv <= 45:
            return "1-й тайм", f"{tv}'"
        if 45 < tv <= 90:
            return "2-й тайм", f"{tv - 45}'"
        if 90 < tv <= 105:
            return "Овертайм", f"{tv - 90}'"
        return "Пенальти", ""
    if "+" in ts:
        left = ts.split("+", 1)[0]
        if left.isdigit():
            return ("1-й тайм" if int(left) <= 45 else "2-й тайм"), f"{ts}'"
    return "", ts


def get_coeff_value(ws_archive, row_idx: int, backup_col: str) -> float:
    v = ws_archive.Range(f"{backup_col}{row_idx}").Value
    try:
        return float(v)
    except (TypeError, ValueError):
        return 1.0


def handle_handicap(forecast: str, team: str, total_home: int, total_away: int, coeff: float) -> Tuple[str, float]:
    start = forecast.find("(")
    end = forecast.find(")")
    if start >= 0 and end > start:
        s = forecast[start + 1:end].replace(",", ".")
    else:
        s = forecast.replace("Ф1", "").replace("Ф2", "").replace(",", ".")
    try:
        handicap = float(s)
    except ValueError:
        handicap = 0.0
    diff = (total_home + handicap - total_away) if team == "HOME" else (total_away + handicap - total_home)
    if diff > 0:
        return "Выигрыш", coeff - 1
    if diff == 0:
        return "Возврат", 0
    return "Проигрыш", -1


def handle_total(forecast: str, total_type: str, total_home: int, total_away: int, coeff: float) -> Tuple[str, float]:
    token = "ТБ" if total_type == "OVER" else "ТМ"
    s = forecast.replace(token, "").replace(",", ".")
    try:
        total_value = float(s)
    except ValueError:
        total_value = 0.0
    match_total = total_home + total_away
    if total_type == "OVER":
        if match_total > total_value:
            return "Выигрыш", coeff - 1
        if match_total == total_value:
            return "Возврат", 0
        return "Проигрыш", -1
    if match_total < total_value:
        return "Выигрыш", coeff - 1
    if match_total == total_value:
        return "Возврат", 0
    return "Проигрыш", -1


def calc_forecast_result(forecast: str, result: str, total_home: int, total_away: int, coeff: float) -> Tuple[str, float]:
    clean = (forecast or "").strip().upper()
    if clean in ("", "-"):
        return "Нет прогноза", 0
    if clean in ("1", "П1"):
        return ("Выигрыш", coeff - 1) if result in ("П1", "1") else ("Проигрыш", -1)
    if clean in ("2", "П2"):
        return ("Выигрыш", coeff - 1) if result in ("П2", "2") else ("Проигрыш", -1)
    if clean in ("Х", "X"):
        return ("Выигрыш", coeff - 1) if result in ("X", "Х") else ("Проигрыш", -1)
    if clean == "1X":
        return ("Выигрыш", coeff - 1) if result in ("П1", "X", "1") else ("Проигрыш", -1)
    if clean == "X2":
        return ("Выигрыш", coeff - 1) if result in ("П2", "X", "2") else ("Проигрыш", -1)
    if clean == "12":
        return ("Выигрыш", coeff - 1) if result in ("П1", "П2", "1", "2") else ("Проигрыш", -1)
    if "Ф1" in clean:
        return handle_handicap(clean, "HOME", total_home, total_away, coeff)
    if "Ф2" in clean:
        return handle_handicap(clean, "AWAY", total_home, total_away, coeff)
    if "ТБ" in clean:
        return handle_total(clean, "OVER", total_home, total_away, coeff)
    if "ТМ" in clean:
        return handle_total(clean, "UNDER", total_home, total_away, coeff)
    if clean == "ОЗ":
        return ("Выигрыш", coeff - 1) if total_home > 0 and total_away > 0 else ("Проигрыш", -1)
    cs = re.match(r"^(\d+)[:\-.](\d+)$", clean)
    if cs:
        ph, pa = int(cs.group(1)), int(cs.group(2))
        won = int(total_home) == ph and int(total_away) == pa
        return ("Выигрыш", coeff - 1) if won else ("Проигрыш", -1)
    return "Неизвестный прогноз", 0


def process_feed_for_sport(ws_archive, sport_id: str, sourcer: str, suffix: str, timezone: int, dayzone: int):
    url = f"https://{sourcer}x/feed/f_{sport_id}_{dayzone}_{timezone}{suffix}"
    feed = fetch_feed(url)

    for fs_index_name, fs_index_value, fields in iter_feed_rows(feed):
        if fs_index_name != "AA":
            continue
        data = parse_fields(fields)
        match_id = data.get("AA", "")
        if not match_id:
            continue
        fcell = ws_archive.Columns("A:A").Find(match_id)
        if fcell is None:
            continue
        row_idx = fcell.Row

        first_home = int(float(data.get("AT", "0") or 0))
        first_away = int(float(data.get("AU", "0") or 0))
        second_home = int(float(data.get("BC", "0") or 0))
        second_away = int(float(data.get("BD", "0") or 0))

        # Keep legacy VBA logic from getScoreHT + sum.
        first_home_adj = first_home - second_home
        first_away_adj = first_away - second_away
        total_home = first_home_adj + second_home
        total_away = first_away_adj + second_away

        match_score = f"{total_home} : {total_away}"
        status_text = STATUSES.get(str(data.get("AC", "")), f"Неизвестный статус ({data.get('AC', '')})")
        period_text, minute_text = parse_match_time(str(data.get("BX", "")))

        ws_archive.Range(f"J{row_idx}").Value = match_score
        ws_archive.Range(f"G{row_idx}").Value = status_text
        ws_archive.Range(f"H{row_idx}").Value = period_text
        ws_archive.Range(f"I{row_idx}").Value = minute_text

        result = "П1" if total_home > total_away else ("П2" if total_home < total_away else "X")
        forecasts = [
            ("K", "M", "N", "L"),  # NTB: forecast, status, profit, coeff
            ("O", "Q", "R", "P"),  # Betalone
            ("S", "U", "V", "T"),  # Sniper
        ]
        for col_forecast, col_status, col_profit, col_coeff in forecasts:
            forecast = ws_archive.Range(f"{col_forecast}{row_idx}").Value
            coeff = get_coeff_value(ws_archive, row_idx, col_coeff)
            status, profit = calc_forecast_result(str(forecast or ""), result, total_home, total_away, coeff)
            ws_archive.Range(f"{col_status}{row_idx}").Value = status
            ws_archive.Range(f"{col_profit}{row_idx}").Value = profit


def run(workbook_path: str) -> int:
    xl = connect_excel()
    wb = open_workbook(xl, workbook_path)

    ws_start = wb.Worksheets("Старт")
    ws_archive = wb.Worksheets("achive")

    time_offset = int(ws_start.Range("AA3").Value or 0)
    timezone = int(ws_start.Range("T2").Value or 0) - (13 + time_offset)
    dayzone = int(ws_start.Range("V2").Value or 0) - 8
    sourcer, suffix = map_source(ws_start.Range("X2").Value)

    last_row = ws_archive.Cells(ws_archive.Rows.Count, "B").End(-4162).Row  # xlUp
    sports = set()
    for r in range(2, last_row + 1):
        v = ws_archive.Range(f"B{r}").Value
        if v not in (None, ""):
            sports.add(str(v))

    for sport_id in sports:
        process_feed_for_sport(ws_archive, sport_id, sourcer, suffix, timezone, dayzone)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.workbook))


if __name__ == "__main__":
    main()
