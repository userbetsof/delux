"""Полный порт VBA getGame: данные → calc (Excel/Python) → опционально архив → БД."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_data import (  # noqa: E402
    MatchInfo,
    build_settings,
    detect_sport_from_match_page,
    load_analysis_data,
)
from calc_backend import get_calc_engine  # noqa: E402
from match_analysis import save_analysis_to_db  # noqa: E402
from match_store import get_queued_match  # noqa: E402
from odds_service import build_fallback_odds, load_odds  # noqa: E402
from settings import DeluxSettings, queue_sport_id  # noqa: E402
from sheets_config import (  # noqa: E402
    SHEET_ANALYSIS,
    SHEET_LIST,
    SHEET_START,
)


def _cell(ws, addr: str):
    return ws.Range(addr).Value


def _safe_str(val) -> str:
    if val is None:
        return ""
    try:
        from date_utils import normalize_match_date

        if hasattr(val, "strftime") or (
            isinstance(val, str)
            and any(ch.isdigit() for ch in val)
            and ("." in val or "-" in val or ":" in val)
        ):
            normalized = normalize_match_date(val)
            if normalized:
                return normalized
    except Exception:
        pass
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y.%m.%d %H:%M")
        except Exception:
            pass
    return str(val).strip()


def _safe_float(val) -> float:
    try:
        if val is None or val == "":
            return 0.0
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val, default: int = 0) -> int:
    try:
        if val is None or val == "":
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default


def find_list_row(ws_list, match_id: str) -> Optional[int]:
    last = ws_list.Cells(ws_list.Rows.Count, "E").End(-4162).Row
    for row in range(2, last + 1):
        if _safe_str(ws_list.Range(f"E{row}").Value) == match_id:
            return row
    return None


def read_match_from_list(wb, match_id: str) -> Tuple[MatchInfo, Dict[str, Any]]:
    ws_list = wb.Worksheets(SHEET_LIST)
    ws_start = wb.Worksheets(SHEET_START)
    row = find_list_row(ws_list, match_id)

    meta: Dict[str, Any] = {
        "list_row": row,
        "sport": _safe_int(_cell(ws_start, "R2"), 1),
        "source": _safe_int(_cell(ws_start, "X2"), 2),
        "tz_base": _safe_int(_cell(ws_start, "T2"), 16),
        "time_offset": _safe_int(_cell(ws_start, "AA3"), 10),
        "list_odds": None,
    }

    match = MatchInfo(match_id=match_id)
    if row is None:
        return match, meta

    match.league = _safe_str(_cell(ws_list, f"A{row}"))
    match.date = _safe_str(_cell(ws_list, f"B{row}"))
    match.home = _safe_str(_cell(ws_list, f"C{row}"))
    match.away = _safe_str(_cell(ws_list, f"D{row}"))
    match.country_id = _safe_str(_cell(ws_list, f"F{row}"))
    try:
        if match.country_id:
            f = float(match.country_id)
            if f == int(f):
                match.country_id = str(int(f))
    except (TypeError, ValueError):
        pass
    match.home_participant_id = _safe_str(_cell(ws_list, f"G{row}"))
    match.away_participant_id = _safe_str(_cell(ws_list, f"H{row}"))
    if match.home_participant_id == match_id:
        match.home_participant_id = ""
    if match.away_participant_id == match_id:
        match.away_participant_id = ""

    sport_u = _safe_int(_cell(ws_list, f"U{row}"), 0)
    if sport_u > 0:
        meta["sport"] = sport_u
        ws_start.Range("R2").Value = sport_u
    else:
        detected = detect_sport_from_match_page(match_id)
        if detected:
            meta["sport"] = detected
            ws_start.Range("R2").Value = detected

    ch = _safe_float(_cell(ws_list, f"O{row}"))
    cd = _safe_float(_cell(ws_list, f"P{row}"))
    ca = _safe_float(_cell(ws_list, f"Q{row}"))
    if ch or cd or ca:
        meta["list_odds"] = (ch, cd, ca)

    ws_list.Range("Y1").Value = match_id
    return match, meta


def _match_from_queue(match_id: str, cfg: DeluxSettings) -> Tuple[MatchInfo, Dict[str, Any]]:
    queued = get_queued_match(match_id)
    meta: Dict[str, Any] = {
        "list_row": None,
        "sport": cfg.sport,
        "source": cfg.source,
        "tz_base": cfg.tz_base,
        "time_offset": cfg.time_offset,
        "list_odds": None,
    }
    if not queued:
        detected = detect_sport_from_match_page(match_id)
        if detected:
            meta["sport"] = detected
        return MatchInfo(match_id=match_id), meta

    match = queued.to_match_info()
    if queued.sport:
        meta["sport"] = queued.sport
    if queued.current_home or queued.current_draw or queued.current_away:
        meta["list_odds"] = (queued.current_home, queued.current_draw, queued.current_away)
    elif queued.start_home or queued.start_draw or queued.start_away:
        meta["list_odds"] = (queued.start_home, queued.start_draw, queued.start_away)
    return match, meta


def get_game(
    workbook: str = "",
    match_id: str = "",
    *,
    do_archive: bool = False,
    do_db: bool = True,
) -> Dict[str, Any]:
    from db import create_database

    cfg = DeluxSettings.from_env()
    workbook_arg = str(workbook or "").strip()
    match_id = match_id.strip()
    if not match_id:
        raise ValueError("match_id пустой")

    xl = None
    wb = None
    ui_state = None
    workbook_path = workbook_arg
    # VBA передаёт --workbook → пишем листы и Excel-пересчёт (иначе Анализ пустой в UI).
    # Headless CLI без --workbook считает Python-calc (кэш формул, без Excel).
    force_excel_ui = bool(workbook_arg)
    need_excel = force_excel_ui or do_archive or cfg.calc_backend == "excel"
    use_excel_engine = force_excel_ui or cfg.calc_backend == "excel"

    try:
        if need_excel:
            from calc_engine import ExcelCalcEngine
            from db import resolve_workbook_path
            from excel_com import connect_excel, open_workbook, restore_excel_ui, snapshot_excel_ui

            workbook_path = (
                resolve_workbook_path(workbook_arg) if workbook_arg else cfg.resolve_calc_workbook()
            )
            xl = connect_excel()
            ui_state = snapshot_excel_ui(xl)
            try:
                if ui_state.get("Visible", True):
                    xl.Visible = True
            except Exception:
                pass
            xl.ScreenUpdating = False
            xl.DisplayAlerts = False
            xl.EnableEvents = False
            wb = open_workbook(xl, workbook_path)
            match, meta = read_match_from_list(wb, match_id)
            # Матчи только в SQLite-очереди (list --db-only) → Список пустой.
            if meta.get("list_row") is None or not (match.home and match.away):
                q_match, q_meta = _match_from_queue(match_id, cfg)
                if q_match.home or q_match.away or q_match.league:
                    match = q_match
                for key in ("sport", "list_odds"):
                    if q_meta.get(key):
                        meta[key] = q_meta[key]
        else:
            match, meta = _match_from_queue(match_id, cfg)

        settings = build_settings(
            sport=meta["sport"],
            source=meta["source"],
            tz_base=meta["tz_base"],
            time_offset=meta["time_offset"],
        )

        print(f"[*] get_game {match_id} sport={settings.sport} {match.home} - {match.away}")
        payload = load_analysis_data(match, settings)
        if need_excel and wb is not None and settings.sport:
            wb.Worksheets(SHEET_START).Range("R2").Value = settings.sport

        code, odds_data = load_odds(match.match_id, settings.source)
        if code != 0 or odds_data is None:
            odds_data = build_fallback_odds(match.match_id)
            if odds_data is None:
                raise RuntimeError(f"odds недоступны для {match_id} (код {code})")
            print(f"[!] {match_id}: fallback odds (код {code})")

        if use_excel_engine and wb is not None and xl is not None:
            from calc_engine import ExcelCalcEngine

            engine = ExcelCalcEngine(workbook_path, xl=xl, wb=wb, manage_ui=False)
            with engine:
                results = engine.run(payload, odds_data, list_odds=meta.get("list_odds"))
        else:
            with get_calc_engine(cfg) as engine:
                results = engine.run(payload, odds_data, list_odds=meta.get("list_odds"))

        print(
            f"[+] calc NTB={results.get('prediction_ntb')} | "
            f"Betalone={results.get('prediction_betalone')} | "
            f"Sniper={results.get('prediction_sniper')}"
        )

        archive_row = None
        if do_archive:
            from archive_excel import archive_match
            from excel_com import connect_excel, open_workbook, snapshot_excel_ui

            if wb is None:
                from db import resolve_workbook_path

                workbook_path = workbook_path or resolve_workbook_path(workbook_arg)
                xl = connect_excel()
                ui_state = snapshot_excel_ui(xl)
                xl.ScreenUpdating = False
                wb = open_workbook(xl, workbook_path)
            archive_row = archive_match(wb, save=True)

        db_sport = queue_sport_id(meta.get("sport") or settings.sport)
        if do_db:
            create_database()
            save_analysis_to_db(
                match_id,
                db_sport,
                results,
                odds_markets=odds_data.all_markets_flat() if odds_data else None,
            )
            print(f"[+] matches.db: {match_id}")

        if wb is not None:
            try:
                wb.Worksheets(SHEET_ANALYSIS).Activate()
            except Exception:
                pass

        results["archive_row"] = archive_row
        results["match_id"] = match_id
        results["sport"] = db_sport
        return results
    finally:
        if xl is not None:
            from excel_com import restore_excel_ui

            try:
                xl.ScreenUpdating = True
                xl.EnableEvents = True
                xl.DisplayAlerts = True
            except Exception:
                pass
            if ui_state is not None:
                restore_excel_ui(xl, {**ui_state, "Visible": True})


def main() -> int:
    parser = argparse.ArgumentParser(description="Python getGame (полный цикл)")
    parser.add_argument("--workbook", default="")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--excel-archive", action="store_true", help="Писать строку в Excel-архив")
    parser.add_argument("--no-archive", action="store_true", help="Не писать Excel-архив")
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args()
    cfg = DeluxSettings.from_env()
    if args.excel_archive:
        do_archive = True
    elif args.no_archive:
        do_archive = False
    else:
        # Из Excel (--workbook) всегда пишем лист achive, как VBA ТоАрхив.
        # Headless без --workbook: архив только при CALC_BACKEND=excel или --excel-archive.
        do_archive = bool(str(args.workbook or "").strip()) or cfg.calc_backend == "excel"
    try:
        get_game(
            args.workbook,
            args.match_id,
            do_archive=do_archive,
            do_db=not args.no_db,
        )
        return 0
    except Exception as exc:
        print(f"[-] get_game failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
