"""Единственная точка зависимости от Excel — пересчёт формул книги."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from analysis_data import AnalysisPayload, MatchInfo
from excel_com import (
    XL_CALC_MANUAL,
    com_retry,
    connect_excel,
    open_workbook,
    restore_excel_ui,
    snapshot_excel_ui,
    _find_open_workbook,
    _norm_path,
    resolve_workbook_path,
)
from odds_service import OddsExcelWriter, OddsSheetData
from sheets_config import (
    SHEET_ANALYSIS,
    SHEET_AWAY,
    SHEET_AWAY_AWAY,
    SHEET_AWAY_HOME,
    SHEET_CALC,
    SHEET_FORM,
    SHEET_H2H,
    SHEET_H2H_HOME,
    SHEET_HOME,
    SHEET_HOME_AWAY,
    SHEET_HOME_HOME,
    SHEET_LIST,
    SHEET_ODDS,
    SHEET_START,
    SHEET_TABLE,
)


def _history_rows(matches) -> List[List]:
    from analysis_data import HistoryMatch

    return [
        [
            m.tour_name,
            m.date,
            m.home_name,
            m.away_name,
            m.home_ht,
            m.away_ht,
            m.home_st,
            m.away_st,
            m.venue,
        ]
        for m in matches
    ]


def _h2h_rows(matches) -> List[List]:
    return [
        [m.tour_name, m.date, m.home_name, m.away_name, m.home_ht, m.away_ht]
        for m in matches
    ]


def _table_rows(rows) -> List[List]:
    return [
        [r.rank, r.team, r.played, r.wins, r.draws, r.losses, r.scored, r.conceded, r.points]
        for r in rows
    ]


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _write_block(ws, start_col: int, start_row: int, rows: List[List]) -> None:
    if not rows:
        return
    end_row = start_row + len(rows) - 1
    end_col = start_col + len(rows[0]) - 1
    addr = f"{_col_letter(start_col)}{start_row}:{_col_letter(end_col)}{end_row}"
    ws.Range(addr).Value = rows


def _safe_float(val) -> float:
    try:
        if val is None or val == "":
            return 0.0
        if isinstance(val, str):
            s = val.strip()
            if not s or s.upper() == "RISK" or s.startswith("#"):
                return 0.0
            return float(s.replace(",", "."))
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _is_excel_error(val) -> bool:
    if val is None or val == "":
        return True
    if isinstance(val, str):
        s = val.strip()
        return (not s) or s.upper() == "RISK" or s.startswith("#")
    return False


def _first_number(*vals) -> float:
    for v in vals:
        if _is_excel_error(v):
            continue
        return _safe_float(v)
    return 0.0


def _find_team_in_table(rows: List[List], team_name: str) -> Optional[List]:
    """Найти строку команды в таблице по имени."""
    team_lower = team_name.casefold()
    for row in rows:
        row_team = (row[1] or "").casefold()
        if team_lower in row_team or row_team in team_lower:
            return row
    return None


def _team_rates(row: List) -> Optional[Tuple[float, float, float]]:
    """Вычислить win/draw/loss rates для одной команды."""
    try:
        played = float(row[2] or 0)
        wins = float(row[3] or 0)
        draws = float(row[4] or 0)
        losses = float(row[5] or 0)
    except (TypeError, ValueError):
        return None

    if played <= 0:
        return None

    return (wins / played, draws / played, losses / played)


def _populate_incognito_data_excel(
    wb, home_team: str, away_team: str,
    overall_rows: List[List], home_rows: List[List], away_rows: List[List],
) -> None:
    """Заполнить Incognito DATA!B2-D11 из Python (минуя VLOOKUP).
    
    Table sheet columns: B=team, C=played, D=wins, E=draws, F=losses,
                         G=scored, H=conceded, I=points
    
    Incognito DATA:
    - B2-D2: overall stats for home team (played, wins, draws)
    - B3-D3: overall stats for away team
    - B4-D4: 3rd team overall stats
    - B5-D5: 4th team overall stats
    - B8-D8: home team stats from HOME table
    - B9-D9, B10-D10, B11-D11: 2nd, 3rd, 4th teams from HOME table
    """
    try:
        ws_inco = wb.Worksheets("Incognito DATA")
    except Exception:
        return

    def _find(rows, name):
        team_lower = name.casefold()
        for row in rows:
            row_team = (row[1] or "").casefold()
            if team_lower in row_team or row_team in team_lower:
                return row
        return None

    def _set_row(row_idx, team_row):
        """B=played(index 2), C=wins(index 3), D=draws(index 4)"""
        if team_row:
            ws_inco.Range(f"B{row_idx}").Value = _safe_float(team_row[2])
            ws_inco.Range(f"C{row_idx}").Value = _safe_float(team_row[3])
            ws_inco.Range(f"D{row_idx}").Value = _safe_float(team_row[4])
        else:
            ws_inco.Range(f"B{row_idx}").Value = 0
            ws_inco.Range(f"C{row_idx}").Value = 0
            ws_inco.Range(f"D{row_idx}").Value = 0

    # Overall: B2-D2 = home, B3-D3 = away
    _set_row(2, _find(overall_rows, home_team))
    _set_row(3, _find(overall_rows, away_team))
    # B4-D4, B5-D5 = 3rd, 4th teams
    if len(overall_rows) > 2:
        _set_row(4, overall_rows[2])
    if len(overall_rows) > 3:
        _set_row(5, overall_rows[3])

    # B8-D11: HOME table stats
    if home_rows:
        _set_row(8, _find(home_rows, home_team))
        for i, row_idx in enumerate((9, 10, 11), start=1):
            if i < len(home_rows):
                _set_row(row_idx, home_rows[i])
            else:
                _set_row(row_idx, None)
    else:
        for row_idx in (8, 9, 10, 11):
            _set_row(row_idx, None)


def _cell_value(ws, addr: str):
    val = ws.Range(addr).Value
    if isinstance(val, int) and val < 0:
        return None
    return val


class ExcelCalcEngine:
    """Пишет входные данные в .xlsm, пересчитывает формулы, читает прогнозы."""

    def __init__(
        self,
        workbook_path: str,
        *,
        xl=None,
        wb=None,
        manage_ui: bool = True,
        fresh: bool = False,
    ):
        self.workbook_path = workbook_path
        self._xl = xl
        self._wb = wb
        self._ui_state = None
        self._manage_ui = manage_ui
        self._owns_session = xl is None
        self._fresh = fresh
        self._prev_calc: int | None = None

    def __enter__(self):
        if self._xl is not None and self._wb is not None:
            if self._manage_ui:
                self._ui_state = snapshot_excel_ui(self._xl)
                try:
                    if self._ui_state.get("Visible"):
                        self._xl.Visible = True
                except Exception:
                    pass
                self._xl.ScreenUpdating = False
                self._xl.DisplayAlerts = False
            return self

        self._xl = connect_excel(fresh=self._fresh)
        self._ui_state = snapshot_excel_ui(self._xl)
        self._xl.ScreenUpdating = False
        self._xl.DisplayAlerts = False
        # Не прячем уже открытую книгу пользователя — иначе Excel «закрывается»
        # и после анализа не возвращается на экран.
        target = _norm_path(resolve_workbook_path(self.workbook_path))
        interactive = _find_open_workbook(self._xl, target) is not None
        if interactive and self._ui_state.get("Visible"):
            self._xl.Visible = True
        else:
            self._xl.Visible = False
        try:
            self._wb = open_workbook(self._xl, self.workbook_path)
        except RuntimeError:
            restore_excel_ui(self._xl, self._ui_state)
            self._xl = connect_excel(fresh=True)
            self._ui_state = snapshot_excel_ui(self._xl)
            self._xl.Visible = False
            self._xl.ScreenUpdating = False
            self._xl.DisplayAlerts = False
            self._wb = open_workbook(self._xl, self.workbook_path)
        self._owns_session = True
        try:
            self._prev_calc = int(self._xl.Calculation)
            self._xl.Calculation = XL_CALC_MANUAL
        except Exception:
            self._prev_calc = None
        try:
            self._xl.EnableEvents = False
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._prev_calc is not None:
            try:
                self._xl.Calculation = self._prev_calc
            except Exception:
                pass
        if self._manage_ui:
            try:
                restore_excel_ui(self._xl, self._ui_state)
            except Exception:
                pass
        if self._owns_session:
            self._xl = None
            self._wb = None
        self._ui_state = None

    @property
    def wb(self):
        if self._wb is None:
            raise RuntimeError("ExcelCalcEngine не открыт (используйте with)")
        return self._wb

    @property
    def xl(self):
        if self._xl is None:
            raise RuntimeError("ExcelCalcEngine не открыт (используйте with)")
        return self._xl

    def clear_parsed_sheets(self) -> None:
        """Очистка + заголовки как VBA clearParsed (иначе ДомаДома/Таблица без шапки)."""
        history_headers = [
            "Чемпионат",
            "Дата/Время",
            "Дома",
            "Гости",
            "К1 в 1Т",
            "К2 в 1Т",
            "К1 во 2Т",
            "К2 во 2Т",
            "Где играли",
        ]
        history_sheets = [
            SHEET_HOME,
            SHEET_HOME_HOME,
            SHEET_HOME_AWAY,
            SHEET_AWAY,
            SHEET_AWAY_HOME,
            SHEET_AWAY_AWAY,
        ]
        for name in history_sheets:
            ws = self.wb.Worksheets(name)
            ws.Columns("A:I").ClearContents()
            for col, title in enumerate(history_headers, start=1):
                ws.Cells(1, col).Value = title

        for name in (SHEET_H2H, SHEET_H2H_HOME):
            self.wb.Worksheets(name).Columns("A:F").ClearContents()

        table_headers = [
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
        for sheet_name in (SHEET_TABLE, SHEET_FORM):
            ws = self.wb.Worksheets(sheet_name)
            ws.Columns("A:AC").ClearContents()
            for start_col in (1, 11, 21):
                for offset, title in enumerate(table_headers):
                    ws.Cells(1, start_col + offset).Value = title

    def write_settings(self, payload: AnalysisPayload) -> None:
        """Старт!R2/X2 — без этого бейсбол/хоккей считаются как футбол."""
        sport = int(getattr(payload.settings, "sport", 1) or 1)
        source = int(getattr(payload.settings, "source", 2) or 2)
        ws = self.wb.Worksheets(SHEET_START)
        ws.Range("R2").Value = sport
        ws.Range("X2").Value = source

    def ensure_list_row(self, match: MatchInfo) -> None:
        """Строка на «Список» для MATCH/INDEX (очередь в БД ≠ лист Excel)."""
        try:
            ws = self.wb.Worksheets(SHEET_LIST)
        except Exception:
            return
        mid = str(match.match_id or "").strip()
        if not mid:
            return
        ws.Range("Y1").Value = mid
        last = ws.Cells(ws.Rows.Count, "E").End(-4162).Row
        if last < 2:
            last = 1
        target = None
        for row in range(2, last + 1):
            if str(ws.Range(f"E{row}").Value or "").strip() == mid:
                target = row
                break
        if target is None:
            target = max(last + 1, 2)
        ws.Range(f"A{target}").Value = match.league or ""
        ws.Range(f"B{target}").Value = match.date or ""
        ws.Range(f"C{target}").Value = match.home or ""
        ws.Range(f"D{target}").Value = match.away or ""
        ws.Range(f"E{target}").Value = mid
        ws.Range(f"F{target}").Value = match.country_id or ""
        if match.home_participant_id:
            ws.Range(f"G{target}").Value = match.home_participant_id
        if match.away_participant_id:
            ws.Range(f"H{target}").Value = match.away_participant_id

    def write_payload(self, payload: AnalysisPayload) -> None:
        self.clear_parsed_sheets()
        match = payload.match
        self.write_settings(payload)
        self.ensure_list_row(match)

        self.wb.Worksheets(SHEET_H2H).Range("A1").Value = match.home
        self.wb.Worksheets(SHEET_H2H).Range("B1").Value = match.away
        self.wb.Worksheets(SHEET_H2H_HOME).Range("A1").Value = match.home
        self.wb.Worksheets(SHEET_H2H_HOME).Range("B1").Value = match.away

        if payload.h2h:
            _write_block(self.wb.Worksheets(SHEET_H2H), 1, 2, _h2h_rows(payload.h2h))
        if payload.h2h_home:
            _write_block(self.wb.Worksheets(SHEET_H2H_HOME), 1, 2, _h2h_rows(payload.h2h_home))

        for sheet_name, rows in (
            (SHEET_HOME, payload.home_all),
            (SHEET_HOME_HOME, payload.home_home),
            (SHEET_HOME_AWAY, payload.home_away),
        ):
            data = _history_rows(rows)
            if data:
                _write_block(self.wb.Worksheets(sheet_name), 1, 2, data)

        for sheet_name, rows in (
            (SHEET_AWAY, payload.away_all),
            (SHEET_AWAY_HOME, payload.away_home),
            (SHEET_AWAY_AWAY, payload.away_away),
        ):
            data = _history_rows(rows)
            if data:
                _write_block(self.wb.Worksheets(sheet_name), 1, 2, data)

        for attr, col in (
            ("table_overall", 1),
            ("table_home", 11),
            ("table_away", 21),
        ):
            rows = _table_rows(getattr(payload, attr))
            if rows:
                _write_block(self.wb.Worksheets(SHEET_TABLE), col, 2, rows)

        for attr, col in (
            ("form_overall", 1),
            ("form_home", 11),
            ("form_away", 21),
        ):
            rows = _table_rows(getattr(payload, attr))
            if rows:
                _write_block(self.wb.Worksheets(SHEET_FORM), col, 2, rows)

        # M26-M28: rates хозяев из home таблицы (M = col 13 on Расчеты)
        # 1PR: Анализ!H24=Расчеты!M26, J24=M28, K24=M27
        # M30-M32: rates гостей из away таблицы (M = col 13 on Расчеты)
        # 5Match: Анализ!H26=Расчеты!M30, J26=M31, K26=M32
        home_rows = _table_rows(payload.table_home)
        away_rows = _table_rows(payload.table_away)
        overall_rows = _table_rows(payload.table_overall)

        ws_calc = self.wb.Worksheets(SHEET_CALC)
        if home_rows:
            home_team_row = _find_team_in_table(home_rows, match.home)
            if home_team_row:
                rates = _team_rates(home_team_row)
                if rates:
                    for row_num, rate in zip((26, 27, 28), rates):
                        ws_calc.Range(f"M{row_num}").Value = rate

        if away_rows:
            away_team_row = _find_team_in_table(away_rows, match.away)
            if away_team_row:
                rates = _team_rates(away_team_row)
                if rates:
                    for row_num, rate in zip((30, 31, 32), rates):
                        ws_calc.Range(f"M{row_num}").Value = rate

        # Incognito DATA!B2-D11: заполняем из Python (минуя VLOOKUP)
        _populate_incognito_data_excel(
            self.wb, match.home, match.away,
            overall_rows, home_rows, away_rows,
        )

        self.wb.Worksheets(SHEET_CALC).Range("A1").Value = match.match_id

        ws_an = self.wb.Worksheets(SHEET_ANALYSIS)
        if match.league:
            ws_an.Range("E2").Value = match.league
        if match.date:
            ws_an.Range("K2").Value = match.date
        if match.home:
            ws_an.Range("E3").Value = match.home
        if match.away:
            ws_an.Range("K3").Value = match.away

    def write_list_odds_1x2(
        self,
        current_home: float,
        current_draw: float,
        current_away: float,
    ) -> None:
        """Стартовые 1X2 с ленты (VBA getOdds → Анализ!B15:D15)."""
        ws_an = self.wb.Worksheets(SHEET_ANALYSIS)
        if current_home:
            ws_an.Range("B15").Value = current_home
        if current_draw:
            ws_an.Range("C15").Value = current_draw
        if current_away:
            ws_an.Range("D15").Value = current_away

    def write_odds(self, odds: OddsSheetData) -> None:
        ws_odds = self.wb.Worksheets(SHEET_ODDS)
        OddsExcelWriter(ws_odds).write(odds)

    def sync_list_participants(self, match: MatchInfo) -> None:
        try:
            ws_list = self.wb.Worksheets(SHEET_LIST)
        except Exception:
            return
        last = ws_list.Cells(ws_list.Rows.Count, "E").End(-4162).Row
        for row in range(2, last + 1):
            if str(ws_list.Range(f"E{row}").Value or "").strip() == match.match_id:
                if match.home_participant_id:
                    ws_list.Range(f"G{row}").Value = match.home_participant_id
                if match.away_participant_id:
                    ws_list.Range(f"H{row}").Value = match.away_participant_id
                break

    def calculate(self) -> None:
        com_retry(lambda: self.xl.CalculateFullRebuild(), attempts=30, delay=0.25)

    def extract_results(self, *, sport: int = 1) -> Dict[str, Any]:
        ws = self.wb.Worksheets(SHEET_ANALYSIS)
        sport = int(sport or 1)

        outcome_probs = []
        for strategy_idx in range(10):
            row = 8 + strategy_idx * 2
            home = _first_number(_cell_value(ws, f"H{row}"), _cell_value(ws, f"I{row}"))
            draw = _first_number(_cell_value(ws, f"J{row}"), _cell_value(ws, f"J{row + 1}"))
            away = _first_number(_cell_value(ws, f"K{row}"), _cell_value(ws, f"L{row}"))
            outcome_probs.append(
                {
                    "strategy_idx": strategy_idx,
                    "home_prob": home,
                    "draw_prob": draw,
                    "away_prob": away,
                }
            )

        from formula_port.incodata_mc import GOAL_BINS

        home_goals = []
        away_goals = []
        try:
            ws_inco = self.wb.Worksheets("IncoData")
            for k in range(GOAL_BINS):
                home_goals.append(_first_number(_cell_value(ws_inco, f"AT{21 + k}")))
                away_goals.append(_first_number(_cell_value(ws_inco, f"AW{21 + k}")))
            if not any(home_goals) and not any(away_goals):
                home_goals = []
                away_goals = []
        except Exception:
            home_goals = []
            away_goals = []
        if not home_goals:
            for col in range(22, 28):
                letter = _col_letter(col)
                home_goals.append(
                    _first_number(_cell_value(ws, f"{letter}10"), _cell_value(ws, f"{letter}11"))
                )
            home_goals = (home_goals + [0.0] * GOAL_BINS)[:GOAL_BINS]
        if not away_goals:
            for col in range(35, 41):
                letter = _col_letter(col)
                away_goals.append(
                    _first_number(_cell_value(ws, f"{letter}10"), _cell_value(ws, f"{letter}11"))
                )
            away_goals = (away_goals + [0.0] * GOAL_BINS)[:GOAL_BINS]

        ntb = str(_cell_value(ws, "S13") or "")
        if sport == 6:
            ntb = ntb.replace("1X", "П1").replace("X2", "П2")

        return {
            "match_date": _cell_value(ws, "K2") or "",
            "league": _cell_value(ws, "E2") or "",
            "home": _cell_value(ws, "E3") or "",
            "away": _cell_value(ws, "K3") or "",
            "prediction_ntb": ntb,
            "prediction_betalone": _cell_value(ws, "O10") or "",
            "prediction_sniper": _cell_value(ws, "X24") or "",
            "outcome_probabilities": outcome_probs,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "sport": sport,
        }

    def run(
        self,
        payload: AnalysisPayload,
        odds: OddsSheetData,
        *,
        list_odds: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        sport = int(getattr(payload.settings, "sport", 1) or 1)

        def _run_once() -> Dict[str, Any]:
            self.write_payload(payload)
            if list_odds:
                self.write_list_odds_1x2(*list_odds)
            self.write_odds(odds)
            self.sync_list_participants(payload.match)
            self.calculate()
            return self.extract_results(sport=sport)

        return com_retry(_run_once, attempts=30, delay=0.25)
