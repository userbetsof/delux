import argparse
import time
from typing import Dict, List

from flashscore_feed import (
    adjust_half_scores,
    clean_team_name,
    fetch_feed,
    format_match_date,
    iter_feed_rows,
    match_list_feed_url,
    odds_list_feed_url,
    parse_fields,
)
from analysis_data import build_settings
from match_store import _league_allowed, filter_matches_for_queue, upsert_matches, _fetch_match_score_from_dc
from settings import DeluxSettings, normalize_sport_id


def _sync_leagues_to_start(ws_start, cfg) -> None:
    """Записать избранные лиги на лист Старт (колонка 27 + sport_id)."""
    for sport_id, leagues in cfg.leagues_by_sport.items():
        if not leagues:
            continue
        col = 27 + int(sport_id)
        ws_start.Cells(1, col).Value = "Лиги"
        last = ws_start.Cells(ws_start.Rows.Count, col).End(-4162).Row
        if last >= 2:
            ws_start.Range(ws_start.Cells(2, col), ws_start.Cells(last, col)).ClearContents()
        for i, name in enumerate(leagues, start=2):
            ws_start.Cells(i, col).Value = name


def filter_championships(ws_start, ws_list, sport_type: int) -> None:
    league_col = 27 + int(sport_type)
    last_row = ws_start.Cells(ws_start.Rows.Count, league_col).End(-4162).Row
    if last_row < 2:
        return

    leagues: List[str] = []
    for r in range(2, last_row + 1):
        value = str(ws_start.Cells(r, league_col).Value or "").strip()
        if value:
            leagues.append(value)

    if ws_list.AutoFilterMode:
        ws_list.AutoFilterMode = False

    if leagues:
        ws_list.Range("A:Q").AutoFilter(Field=1, Criteria1=leagues, Operator=7)
    else:
        ws_list.Range("A:Q").AutoFilter(Field=1, Criteria1="<>")


def parse_matches_feed(feed_text: str, timezone: int, time_offset: int) -> List[Dict]:
    matches: List[Dict] = []
    tour_name = ""
    country_id = ""

    for fs_index_name, _fs_index_value, fields in iter_feed_rows(feed_text):
        data = parse_fields(fields)
        if fs_index_name == "ZA":
            tour_name = (data.get("ZA", "") or "").replace(" - Плей-офф", "")
            country_id = data.get("ZB", "")
            continue
        if fs_index_name != "AA":
            continue

        home_name = clean_team_name(data.get("AE", ""))
        away_name = clean_team_name(data.get("AF", ""))
        if not tour_name or not home_name:
            continue

        home_first = int(float(data.get("AT", "0") or 0))
        away_first = int(float(data.get("AU", "0") or 0))
        home_second = int(float(data.get("BC", "0") or 0))
        away_second = int(float(data.get("BD", "0") or 0))
        
        # Проверяем: если AT/AU уже полные таймы (больше BC/BD), используем их напрямую
        status_game = str(data.get("AB", ""))
        status_game_code = str(data.get("AC", ""))
        is_finished = status_game == "3" and status_game_code in ("3", "10", "11")
        score_home = None
        score_away = None
        if is_finished:
            # Для прошедших матчей счёт будет подтянут из dc_ feed
            # (в tr_ feed счёт может быть неполным — только первый тайм)
            pass
        elif home_first > home_second and away_first > away_second:
            # AT/AU — полные таймы, BC/BD — второй тайм
            score_home = home_first
            score_away = away_first
        else:
            # AT/AU — первый тайм, BC/BD — второй тайм
            score_home = home_first + home_second
            score_away = away_first + away_second

        matches.append(
            {
                "tour_name": tour_name,
                "date_match": format_match_date(data.get("AD", ""), timezone, time_offset),
                "start_ts": int(float(data.get("AD", "0") or 0)) or None,
                "home_name": home_name,
                "away_name": away_name,
                "match_id": data.get("AA", ""),
                "country_id": country_id,
                "score_home": score_home,
                "score_away": score_away,
                "is_finished": is_finished,
            }
        )
    return matches


def parse_odds_feed(feed_text: str) -> Dict[str, Dict[str, float]]:
    odds_by_match: Dict[str, Dict[str, float]] = {}
    match_id = ""

    for fs_index_name, _fs_index_value, fields in iter_feed_rows(feed_text):
        data = parse_fields(fields)
        if fs_index_name == "AA":
            match_id = data.get("AA", "")
            if not match_id:
                continue
            try:
                start_home = float(data.get("XA", "0") or 0)
            except ValueError:
                start_home = 0.0
            if start_home <= 0:
                continue
            odds_by_match[match_id] = {
                "start_home": start_home,
                "start_draw": float(data.get("XB", "0") or 0),
                "start_away": float(data.get("XC", "0") or 0),
                "current_home": float(data.get("YA", "0") or 0),
                "current_draw": float(data.get("YB", "0") or 0),
                "current_away": float(data.get("YC", "0") or 0),
            }
    return odds_by_match


def add_load_hyperlinks(ws_list, start_row: int, end_row: int) -> None:
    for row in range(start_row, end_row + 1):
        cell = ws_list.Range(f"I{row}")
        try:
            cell.Hyperlinks(1).Delete()
        except Exception:
            pass
        cell.Value = "Загрузить"
        ws_list.Hyperlinks.Add(Anchor=cell, Address="", TextToDisplay="Загрузить")


def write_matches(ws_list, start_row: int, matches: List[Dict], sport_id: int = 1) -> int:
    if not matches:
        return start_row

    rows = []
    for match in matches:
        score_home = match["score_home"] if match["score_home"] is not None else ""
        score_away = match["score_away"] if match["score_away"] is not None else ""
        rows.append(
            [
                match["tour_name"],
                match["date_match"],
                match["home_name"],
                match["away_name"],
                match["match_id"],
                match["country_id"],
                "",
                "",
                "",
                score_home,
                score_away,
            ]
        )

    end_row = start_row + len(rows) - 1

    def _write() -> None:
        ws_list.Range(f"A{start_row}:K{end_row}").Value = rows
        # U = sport_id одним блоком
        sport_col = [[int(sport_id)] for _ in rows]
        ws_list.Range(f"U{start_row}:U{end_row}").Value = sport_col
        if start_row == 2:
            ws_list.Range("U1").Value = "Sport_ID"

    from excel_com import com_retry

    com_retry(_write)
    return end_row + 1


def apply_odds(ws_list, odds_by_match: Dict[str, Dict[str, float]]) -> None:
    last_row = int(ws_list.Cells(ws_list.Rows.Count, "E").End(-4162).Row)
    if last_row < 2:
        return

    def _read_ids():
        return ws_list.Range(f"E2:E{last_row}").Value

    from excel_com import com_retry

    raw_ids = com_retry(_read_ids)
    if raw_ids is None:
        return
    if last_row == 2:
        raw_ids = ((raw_ids,),)

    values = []
    for cell in raw_ids:
        match_id = str((cell[0] if cell else "") or "")
        odds = odds_by_match.get(match_id) or {}
        values.append(
            [
                odds.get("start_home", ""),
                odds.get("start_draw", ""),
                odds.get("start_away", ""),
                odds.get("current_home", ""),
                odds.get("current_draw", ""),
                odds.get("current_away", ""),
            ]
        )

    def _write_odds() -> None:
        ws_list.Range(f"L2:Q{last_row}").Value = values

    com_retry(_write_odds)


def sort_range(ws_list, start_row: int, end_row: int) -> None:
    if end_row < start_row:
        return
    ws_list.Range(f"A{start_row}:Q{end_row}").Sort(
        Key1=ws_list.Columns(2),
        Order1=1,
        Header=0,
    )


def _enrich_scores_from_dc(matches: List[Dict], sport_id: int) -> None:
    """Подтянуть полный счёт из dc_ feed для прошедших матчей.
    
    Для прошедших матчей (is_finished=True) счёт из tr_ feed может быть
    неполным (только первый тайм). Берём полный счёт из dc_ feed (DE/DF).
    """
    for match in matches:
        match_id = match.get("match_id", "")
        # Для прошедших матчей — всегда подтягиваем из dc_ feed
        if match.get("is_finished"):
            sh, sa = _fetch_match_score_from_dc(match_id, sport_id)
            if sh is not None and sa is not None:
                match["score_home"] = sh
                match["score_away"] = sa
        else:
            # Для предстоящих/live — подтягиваем только если нет счёта
            score_home = match.get("score_home")
            score_away = match.get("score_away")
            if score_home is None and score_away is None:
                sh, sa = _fetch_match_score_from_dc(match_id, sport_id)
                if sh is not None and sa is not None:
                    match["score_home"] = sh
                    match["score_away"] = sa


def _enrich_with_odds(
    matches: List[Dict],
    sport_id: int,
    dayzone: int,
    timezone: int,
    sourcer: str,
    suffix: str,
) -> None:
    odds_url = odds_list_feed_url(sport_id, dayzone, timezone, sourcer=sourcer, suffix=suffix)
    try:
        odds_by_match = parse_odds_feed(fetch_feed(odds_url))
    except Exception as exc:
        print(f"[!] sport={sport_id}: коэффициенты недоступны ({exc})")
        return
    for match in matches:
        odds = odds_by_match.get(match["match_id"])
        if not odds:
            continue
        match["start_home"] = odds["start_home"]
        match["start_draw"] = odds["start_draw"]
        match["start_away"] = odds["start_away"]
        match["current_home"] = odds["current_home"]
        match["current_draw"] = odds["current_draw"]
        match["current_away"] = odds["current_away"]


def _fetch_sport_matches(
    sport_id: int,
    sourcer: str,
    suffix: str,
    timezone: int,
    dayzone: int,
    time_offset: int,
) -> List[Dict]:
    feed_url = match_list_feed_url(sport_id, dayzone, timezone, sourcer=sourcer, suffix=suffix)
    matches = parse_matches_feed(fetch_feed(feed_url), timezone, time_offset)
    _enrich_scores_from_dc(matches, sport_id)
    _enrich_with_odds(matches, sport_id, dayzone, timezone, sourcer, suffix)
    return matches


def run(
    workbook_path: str = "",
    auto: bool | None = None,
    *,
    db_only: bool = True,
) -> int:
    cfg = DeluxSettings.from_env()
    if auto is None:
        auto = cfg.list_auto_default()
    ms = cfg.match_settings
    sports = cfg.sports_auto if auto else [cfg.sport]

    total_written = 0
    for idx, sport_id in enumerate(sports):
        fetch_sport_id = normalize_sport_id(sport_id)
        try:
            matches = _fetch_sport_matches(
                fetch_sport_id,
                ms.sourcer,
                ms.suffix,
                cfg.timezone,
                cfg.dayzone,
                cfg.time_offset,
            )
        except Exception as exc:
            print(f"[-] sport={sport_id}: лента недоступна ({exc})")
            matches = []
        ms_sport = build_settings(
            sport=sport_id,
            source=cfg.source,
            tz_base=cfg.tz_base,
            dayzone_base=cfg.dayzone_base,
            time_offset=cfg.time_offset,
        )
        matches, skip_league, skip_tour = filter_matches_for_queue(
            matches,
            sport_id,
            leagues=cfg.leagues_for_sport(sport_id),
            min_games=cfg.min_tour_games,
            settings=ms_sport,
        )
        if skip_league or skip_tour:
            print(
                f"[*] sport={sport_id}: пропущено лиг={skip_league}, "
                f"тур<{cfg.min_tour_games}={skip_tour}"
            )
        written = upsert_matches(
            matches,
            sport_id,
            leagues=cfg.leagues_for_sport(sport_id),
            replace_sport=True,
        )
        total_written += written
        print(f"[+] sport={sport_id}: {written} матчей в БД")

    if db_only:
        print(f"[+] Всего в очереди: {total_written}")
        return 0

    from excel_com import connect_excel, open_workbook, resolve_workbook_path

    if not workbook_path:
        workbook_path = cfg.resolve_calc_workbook()
    workbook_path = resolve_workbook_path(workbook_path)

    xl = connect_excel()
    prev_calc = None
    try:
        xl.Visible = True
        try:
            prev_calc = xl.Calculation
            xl.Calculation = -4135  # xlManual
        except Exception:
            pass
        xl.ScreenUpdating = False
        xl.EnableEvents = False
        xl.DisplayAlerts = False
    except Exception:
        pass
    wb = open_workbook(xl, workbook_path)
    ws_start = wb.Worksheets("Старт")
    ws_list = wb.Worksheets("Список")
    try:
        if ws_list.AutoFilterMode:
            ws_list.AutoFilterMode = False
    except Exception:
        pass
    try:
        xl.StatusBar = False
    except Exception:
        pass

    ws_start.Range("R2").Value = cfg.sport
    ws_start.Range("X2").Value = cfg.source
    ws_start.Range("T2").Value = cfg.tz_base
    ws_start.Range("V2").Value = cfg.dayzone_base
    ws_start.Range("AA3").Value = cfg.time_offset
    _sync_leagues_to_start(ws_start, cfg)

    next_row = 2
    for idx, sport_id in enumerate(sports):
        fetch_sport_id = normalize_sport_id(sport_id)
        try:
            matches = _fetch_sport_matches(
                fetch_sport_id,
                ms.sourcer,
                ms.suffix,
                cfg.timezone,
                cfg.dayzone,
                cfg.time_offset,
            )
        except Exception as exc:
            print(f"[-] sport={sport_id}: feed unavailable ({exc})")
            matches = []
        sport_leagues = cfg.leagues_for_sport(sport_id)
        ms_sport = build_settings(
            sport=sport_id,
            source=cfg.source,
            tz_base=cfg.tz_base,
            dayzone_base=cfg.dayzone_base,
            time_offset=cfg.time_offset,
        )
        filtered, skip_league, skip_tour = filter_matches_for_queue(
            matches,
            sport_id,
            leagues=sport_leagues,
            min_games=cfg.min_tour_games,
            settings=ms_sport,
        )
        if skip_league or skip_tour:
            print(
                f"[*] sport={sport_id}: пропущено лиг={skip_league}, "
                f"тур<{cfg.min_tour_games}={skip_tour}"
            )
        if idx == 0:
            last_row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row
            if last_row >= 2:
                ws_list.Rows(f"2:{last_row}").Delete()
            row = 2
        else:
            row = ws_list.Cells(ws_list.Rows.Count, "A").End(-4162).Row + 1
            if row < 2:
                row = 2

        if not filtered:
            print(f"[!] sport={sport_id}: 0 matches after league filter (raw={len(matches)})")
            continue
        sport_start = row
        row = write_matches(ws_list, row, filtered, sport_id=sport_id)
        odds_by_match = {
            m["match_id"]: {
                "start_home": m.get("start_home", 0),
                "start_draw": m.get("start_draw", 0),
                "start_away": m.get("start_away", 0),
                "current_home": m.get("current_home", 0),
                "current_draw": m.get("current_draw", 0),
                "current_away": m.get("current_away", 0),
            }
            for m in filtered
        }
        apply_odds(ws_list, odds_by_match)
        sort_range(ws_list, sport_start, row - 1)
        add_load_hyperlinks(ws_list, sport_start, row - 1)
        next_row = row
        print(f"[+] sport={sport_id}: {len(filtered)} rows -> List")

    ws_start.Range("R2").Value = cfg.sport
    # AutoFilter по лигам одного спорта ломает multi-sport Список (остаётся фильтр последнего).
    try:
        if ws_list.AutoFilterMode:
            ws_list.AutoFilterMode = False
    except Exception:
        pass
    if len(sports) == 1:
        filter_championships(ws_start, ws_list, sports[0])
    else:
        # Показать все загруженные виды; фильтр — вручную / по кнопке.
        try:
            ws_list.Range("A:Q").AutoFilter(Field=1, Criteria1="<>")
        except Exception:
            pass
    try:
        wb.Save()
    except Exception as exc:
        print(f"[!] Save workbook: {exc}")
    try:
        if prev_calc is not None:
            xl.Calculation = prev_calc
        xl.EnableEvents = True
        xl.ScreenUpdating = True
        xl.Visible = True
        ws_list.Activate()
    except Exception:
        pass
    print(f"[+] Список обновлён, строк данных: {max(next_row - 2, 0)}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", default="")
    parser.add_argument(
        "--auto",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Все виды из DELUX_SPORTS_AUTO (по умолчанию: да, если их >1)",
    )
    parser.add_argument("--excel", action="store_true", help="Писать лист «Список» в Excel")
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Только очередь в БД (без Excel). По умолчанию так, если нет --workbook/--excel",
    )
    args = parser.parse_args()
    # VBA getMS передаёт --workbook: всегда пишем Список, если не указан явный --db-only.
    if args.db_only and not args.excel:
        db_only = True
    elif args.excel or args.workbook:
        db_only = False
    else:
        db_only = True
    raise SystemExit(
        run(
            workbook_path=args.workbook,
            auto=args.auto,
            db_only=db_only,
        )
    )


if __name__ == "__main__":
    main()
