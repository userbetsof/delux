import argparse
import re
from typing import Optional


MAPPING = {
    "П1": "1X2_1",
    "П2": "1X2_2",
    "X": "1X2_X",
    "ОЗ": "BTTS_YES",
    "1X": "DC_1X",
    "12": "DC_12",
    "X2": "DC_X2",
}

ODDS_FIRST_BK_COL = 3
ODDS_BK_COLS = 3
ODDS_DATA_START_ROW = 3
ODDS_SUBHEADER_ROW = 2


def get_last_col(ws):
    return ws.Cells(ODDS_SUBHEADER_ROW, ws.Columns.Count).End(-4159).Column  # xlToLeft


def get_last_row(ws, last_col: int) -> int:
    last_row = ODDS_DATA_START_ROW
    col = ODDS_FIRST_BK_COL
    while col <= last_col:
        r = ws.Cells(ws.Rows.Count, col).End(-4162).Row  # xlUp
        if r > last_row:
            last_row = r
        col += ODDS_BK_COLS
    return last_row


def find_max_market_odds(ws_odds, market_name: str, value_type: str = "CURRENT") -> float:
    last_col = get_last_col(ws_odds)
    if last_col < ODDS_FIRST_BK_COL:
        return 0.0

    last_row = get_last_row(ws_odds, last_col)
    val_col_offset = 1 if value_type.upper() == "OPEN" else 2
    exact_match = "*" not in market_name
    best: Optional[float] = None

    start_col = ODDS_FIRST_BK_COL
    while start_col <= last_col:
        r = ODDS_DATA_START_ROW
        while r <= last_row:
            cell_market = str(ws_odds.Cells(r, start_col).Value or "").strip()
            if not cell_market:
                break

            if exact_match:
                ok = cell_market.lower() == market_name.lower()
            else:
                ok = market_name.lower() in cell_market.lower()

            if ok:
                v = ws_odds.Cells(r, start_col + val_col_offset).Value
                try:
                    fv = float(v)
                    if best is None or fv > best:
                        best = fv
                except (TypeError, ValueError):
                    pass
            r += 1
        start_col += ODDS_BK_COLS
    return best if best is not None else 0.0


def find_by_pattern(coeff_name: str, ws_odds) -> float:
    if "ТБ" in coeff_name:
        line = coeff_name.replace("ТБ", "").strip().replace(",", ".")
        return find_max_market_odds(ws_odds, f"OVER {line}", "CURRENT")
    if "ТМ" in coeff_name:
        line = coeff_name.replace("ТМ", "").strip().replace(",", ".")
        return find_max_market_odds(ws_odds, f"UNDER {line}", "CURRENT")
    if "Ф1" in coeff_name:
        m = re.search(r"\(([-+]?\d+(?:[.,]\d+)?)\)", coeff_name)
        if m:
            line = m.group(1).replace(",", ".")
            return find_max_market_odds(ws_odds, f"HANDICAP HOME {line}", "CURRENT")
    if "Ф2" in coeff_name:
        m = re.search(r"\(([-+]?\d+(?:[.,]\d+)?)\)", coeff_name)
        if m:
            line = m.group(1).replace(",", ".")
            return find_max_market_odds(ws_odds, f"HANDICAP AWAY {line}", "CURRENT")
    return 0.0


def find_single_coefficient(coeff_name: str, ws_odds) -> float:
    name = (coeff_name or "").strip()
    if not name or name == "-":
        return 0.0

    mapped = MAPPING.get(name)
    if mapped:
        v = find_max_market_odds(ws_odds, mapped, "CURRENT")
        if v > 0:
            return v

    v = find_by_pattern(name, ws_odds)
    if v > 0:
        return v

    return find_max_market_odds(ws_odds, name, "CURRENT")


def calc_prediction_value(prediction: str, ws_odds) -> Optional[float]:
    text = (prediction or "").strip()
    if not text or text == "-":
        return None

    if "+" in text:
        total = 1.0
        for part in [p.strip() for p in text.split("+") if p.strip()]:
            v = find_single_coefficient(part, ws_odds)
            if v <= 0:
                return None
            total *= v
        return total

    v = find_single_coefficient(text, ws_odds)
    return v if v > 0 else None


def update_coefficients(workbook_path: str, target_row: int) -> int:
    import win32com.client

    try:
        xl = win32com.client.GetObject(Class="Excel.Application")
    except Exception:
        xl = win32com.client.Dispatch("Excel.Application")
    wb = None
    for w in xl.Workbooks:
        if str(w.FullName).lower() == workbook_path.lower():
            wb = w
            break
    if wb is None:
        wb = xl.Workbooks.Open(workbook_path)

    ws_analysis = wb.Worksheets("Анализ")
    ws_odds = wb.Worksheets("Коэффициенты")
    ws_archive = wb.Worksheets("achive")

    ntb = calc_prediction_value(ws_analysis.Range("S13").Value, ws_odds)
    sniper = calc_prediction_value(ws_analysis.Range("X24").Value, ws_odds)
    betalone = calc_prediction_value(ws_analysis.Range("O10").Value, ws_odds)

    ws_archive.Range(f"L{target_row}").Value = ntb if ntb is not None else ""
    ws_archive.Range(f"T{target_row}").Value = sniper if sniper is not None else ""
    ws_archive.Range(f"P{target_row}").Value = betalone if betalone is not None else ""
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--row", type=int, required=True)
    args = parser.parse_args()
    raise SystemExit(update_coefficients(args.workbook, args.row))


if __name__ == "__main__":
    main()
