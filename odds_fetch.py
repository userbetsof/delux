"""CLI-обёртка odds_fetch → odds_service + опционально Excel."""

import argparse

from excel_com import connect_excel, open_workbook
from odds_service import OddsExcelWriter, load_odds
from settings import DeluxSettings


def update_odds(workbook_path: str, event_id: str, source_value=None) -> int:
    cfg = DeluxSettings.from_env()
    source = source_value if source_value is not None else cfg.source
    code, data = load_odds(event_id, source)
    if code != 0 or data is None:
        return code

    xl = connect_excel()
    wb = open_workbook(xl, workbook_path)
    ws_odds = wb.Worksheets("Коэффициенты")
    OddsExcelWriter(ws_odds).write(data)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", default="")
    parser.add_argument("--event-id", required=True)
    args = parser.parse_args()
    cfg = DeluxSettings.from_env()
    workbook = args.workbook or cfg.resolve_calc_workbook()
    raise SystemExit(update_odds(workbook, args.event_id))


if __name__ == "__main__":
    main()
