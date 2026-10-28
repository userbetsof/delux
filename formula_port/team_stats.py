"""Запись входных данных матча в CellStore (замена write_payload)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from analysis_data import AnalysisPayload, HistoryMatch, TableRow
from formula_port.cell_store import CellStore
from odds_service import OddsSheetData
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

HISTORY_HEADERS = [
    "Чемпионат",
    "Дома",        # B — для MATCH/VLOOKUP (Incognito DATA!I2: MATCH(A1,Дома!B:B))
    "Дата/Время",
    "Гости",
    "К1 в 1Т",
    "К2 в 1Т",
    "К1 во 2Т",
    "К2 во 2Т",
    "Где играли",
]

TABLE_HEADERS = [
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

HISTORY_SHEETS = (
    SHEET_HOME,
    SHEET_HOME_HOME,
    SHEET_HOME_AWAY,
    SHEET_AWAY,
    SHEET_AWAY_HOME,
    SHEET_AWAY_AWAY,
)


def _history_rows(matches: List[HistoryMatch]) -> List[List]:
    return [
        [
            m.tour_name,
            m.home_name,   # B — для MATCH/VLOOKUP
            m.date,
            m.away_name,
            m.home_ht,
            m.away_ht,
            m.home_st,
            m.away_st,
            m.venue,
        ]
        for m in matches
    ]


def _h2h_rows(matches: List[HistoryMatch]) -> List[List]:
    return [
        [m.tour_name, m.date, m.home_name, m.away_name, m.home_ht, m.away_ht]
        for m in matches
    ]


def _safe_float(val) -> float:
    """Безопасно преобразовать значение в float."""
    try:
        if val is None or val == "":
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _populate_incognito_data(
    store: CellStore,
    rows: List[List],
    home_team: str,
    away_team: str,
    home_rows: Optional[List[List]] = None,
    away_rows: Optional[List[List]] = None,
) -> None:
    """Заполнить Incognito DATA!B2-D11 значениями из Python (минуя VLOOKUP).
    
    VLOOKUP($A$1, Таблица!$B:$I, COLUMN(), FALSE) не работает, т.к. match_id
    отсутствует в столбце B таблицы. Заполняем значения напрямую.
    
    Структура Incognito DATA:
    - B2-D2: row 2 of Table sheet (overall, first team row)
    - B3-D3: row 3 of Table sheet
    - B4-D4: row 4 of Table sheet
    - B5-D5: row 5 of Table sheet
    - B8-D8: row 2 of Home table (home team stats)
    - B9-D9: row 3 of Home table
    - B10-D10: row 4 of Home table
    - B11-D11: row 5 of Home table
    
    Но на самом деле B2-D2 = VLOOKUP(match_id, Таблица!B:I, 2, FALSE)
    где COLUMN()=2 для B, 3 для C, 4 для D.
    Таблица!B:I: B=team, C=played, D=wins, E=draws, F=losses, G=scored, H=conceded, I=points
    
    Так как match_id нет в таблице, заполняем значения для home и away команд.
    """
    if not rows:
        return
    
    # Найти строки home и away команд в overall таблице
    home_row = _find_team_in_table(rows, home_team)
    away_row = _find_team_in_table(rows, away_team)
    
    # Заполняем B2-D2 для home команды, B3-D3 для away команды
    # B = column 2 of Table sheet (team name)
    # C = column 3 of Table sheet (played)
    # D = column 4 of Table sheet (wins)
    # Но VLOOKUP($A$1, Таблица!$B:$I, 2, FALSE) ищет match_id в столбце B,
    # а возвращает значение из столбца B+2-1 = C (played).
    # Так как match_id нет, заполняем:
    # B2 = played (column C of Table sheet)
    # C2 = wins (column D of Table sheet)
    # D2 = draws (column E of Table sheet)
    
    def _set_incognito_row(row_idx: int, team_row: Optional[List]) -> None:
        """Заполнить Incognito DATA!B{row_idx}-D{row_idx}.
        
        row_idx: номер строки в Incognito DATA (2, 3, 4, 5, 8, 9, 10, 11)
        team_row: строка из таблицы [rank, team, played, wins, draws, losses, scored, conceded, points]
        """
        if team_row:
            # B = played (index 2), C = wins (index 3), D = draws (index 4)
            # Но VLOOKUP($A$1, Таблица!$B:$I, 2, FALSE) возвращает column 2 of range = column C of Table = played
            # VLOOKUP($A$1, Таблица!$B:$I, 3, FALSE) возвращает column 3 of range = column D of Table = wins
            # VLOOKUP($A$1, Таблица!$B:$I, 4, FALSE) возвращает column 4 of range = column E of Table = draws
            store.set_value("Incognito DATA", f"B{row_idx}", _safe_float(team_row[2]))  # played
            store.set_value("Incognito DATA", f"C{row_idx}", _safe_float(team_row[3]))  # wins
            store.set_value("Incognito DATA", f"D{row_idx}", _safe_float(team_row[4]))  # draws
        else:
            store.set_value("Incognito DATA", f"B{row_idx}", 0)
            store.set_value("Incognito DATA", f"C{row_idx}", 0)
            store.set_value("Incognito DATA", f"D{row_idx}", 0)
    
    # Overall rows: B2-D2 = home team, B3-D3 = away team, B4-D4 = 3rd team, B5-D5 = 4th team
    _set_incognito_row(2, home_row)
    _set_incognito_row(3, away_row)
    # B4-D4, B5-D5 = 3rd and 4th teams (or 0 if not found)
    if len(rows) > 2:
        _set_incognito_row(4, rows[2])
    if len(rows) > 3:
        _set_incognito_row(5, rows[3])

    # B8-D11: home team stats from HOME table (for 5Match strategy)
    if home_rows:
        home_team_home_row = _find_team_in_table(home_rows, home_team)
        _set_incognito_row(8, home_team_home_row)
        # B9-D9, B10-D10, B11-D11 = 2nd, 3rd, 4th teams from home table
        for i, row_idx in enumerate((9, 10, 11), start=1):
            if i < len(home_rows):
                _set_incognito_row(row_idx, home_rows[i])
            else:
                _set_incognito_row(row_idx, None)
    else:
        for row_idx in (8, 9, 10, 11):
            _set_incognito_row(row_idx, None)


def _table_rows(rows: List[TableRow]) -> List[List]:
    return [
        [r.rank, r.team, r.played, r.wins, r.draws, r.losses, r.scored, r.conceded, r.points]
        for r in rows
    ]


def _compute_avg_rates(rows: List[List]) -> Optional[Tuple[float, float, float]]:
    """Вычислить средние win/draw/loss rates из строк таблицы."""
    total_win_rate = 0.0
    total_draw_rate = 0.0
    total_away_rate = 0.0
    count = 0

    for row in rows:
        # row: [rank, team, played, wins, draws, losses, scored, conceded, points]
        try:
            played = float(row[2] or 0)
            wins = float(row[3] or 0)
            draws = float(row[4] or 0)
            losses = float(row[5] or 0)
        except (TypeError, ValueError):
            continue

        if played <= 0:
            continue

        total_win_rate += wins / played
        total_draw_rate += draws / played
        total_away_rate += losses / played
        count += 1

    if count == 0:
        return None

    return (total_win_rate / count, total_draw_rate / count, total_away_rate / count)


def _find_team_in_table(rows: List[List], team_name: str) -> Optional[List]:
    """Найти строку команды в таблице по имени."""
    team_lower = team_name.casefold()
    for row in rows:
        # row: [rank, team, played, wins, draws, losses, scored, conceded, points]
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


def _fill_5match_stats(store: CellStore, rows: List[List], col_start: int, target_rows: Tuple[int, ...]) -> None:
    """Заполнить指定的 M* ячейки win/draw/loss rates.

    Args:
        store: CellStore
        rows: строки таблицы (из _table_rows)
        col_start: стартовая колонка таблицы (1=A для overall, 11=K для home, 21=U для away)
        target_rows: какие строки M* заполнять (например, (26, 27, 28) или (30, 31, 32))

    M-колонка = col_start + 2 (3-я колонка таблицы: Игр).
    Для overall: col_start=1 → M=col 3 (C)
    Для home: col_start=11 → M=col 13 (M)
    Для away: col_start=21 → M=col 23 (W)
    """
    if not rows:
        return

    rates = _compute_avg_rates(rows)
    if rates is None:
        return

    avg_win, avg_draw, avg_away = rates

    # M-колонка = col_start + 2 (3-я колонка таблицы: Игр)
    m_col = col_start + 2

    for row_num, rate in zip(target_rows, rates):
        store.set_value(SHEET_TABLE, f"{_col(m_col)}{row_num}", rate)


def _write_history_headers(store: CellStore) -> None:
    for sheet_name in HISTORY_SHEETS:
        store.set_range(sheet_name, 1, 1, [HISTORY_HEADERS])


def _write_table_headers(store: CellStore) -> None:
    for sheet_name in (SHEET_TABLE, SHEET_FORM):
        for start_col in (1, 11, 21):
            store.set_range(sheet_name, 1, start_col, [TABLE_HEADERS])


def apply_list_row(store: CellStore, payload: AnalysisPayload) -> None:
    """Одна строка «Список» — для MATCH(A1, Список!E:E) / INDEX на лиге и дате."""
    match = payload.match
    store.set_value(SHEET_LIST, "A2", match.league or "")
    store.set_value(SHEET_LIST, "B2", match.date or "")
    store.set_value(SHEET_LIST, "C2", match.home or "")
    store.set_value(SHEET_LIST, "D2", match.away or "")
    store.set_value(SHEET_LIST, "E2", match.match_id)
    store.set_value(SHEET_LIST, "F2", match.country_id or "")
    store.set_value(SHEET_LIST, "G2", match.home_participant_id or "")
    store.set_value(SHEET_LIST, "H2", match.away_participant_id or "")
    store.set_value(SHEET_LIST, "Y1", match.match_id)


def apply_payload_to_store(store: CellStore, payload: AnalysisPayload) -> None:
    """Пишет сырые данные матча в листы-входы (как calc_engine.write_payload)."""
    match = payload.match
    _write_history_headers(store)
    _write_table_headers(store)
    apply_list_row(store, payload)

    store.set_value(SHEET_H2H, "A1", match.home)
    store.set_value(SHEET_H2H, "B1", match.away)
    store.set_value(SHEET_H2H_HOME, "A1", match.home)
    store.set_value(SHEET_H2H_HOME, "B1", match.away)

    if payload.h2h:
        store.set_range(SHEET_H2H, 2, 1, _h2h_rows(payload.h2h))
    if payload.h2h_home:
        store.set_range(SHEET_H2H_HOME, 2, 1, _h2h_rows(payload.h2h_home))

    for sheet_name, rows in (
        (SHEET_HOME, payload.home_all),
        (SHEET_HOME_HOME, payload.home_home),
        (SHEET_HOME_AWAY, payload.home_away),
        (SHEET_AWAY, payload.away_all),
        (SHEET_AWAY_HOME, payload.away_home),
        (SHEET_AWAY_AWAY, payload.away_away),
    ):
        data = _history_rows(rows)
        if data:
            store.set_range(sheet_name, 2, 1, data)

    # Заполняем M26-M32 для конкретных команд матча:
    # M26-M28 — win/draw/loss rates хозяев (из home таблицы)
    # M30-M32 — win/draw/loss rates гостей (из away таблицы)

    # M26-M28: rates хозяев из home таблицы
    overall_rows = _table_rows(payload.table_overall)
    home_rows = _table_rows(payload.table_home)
    away_rows = _table_rows(payload.table_away)

    if home_rows:
        store.set_range(SHEET_TABLE, 2, 11, home_rows)
    if away_rows:
        store.set_range(SHEET_TABLE, 2, 21, away_rows)
    if overall_rows:
        store.set_range(SHEET_TABLE, 2, 1, overall_rows)
    
    # Заполняем Incognito DATA!B2-D11 значениями из Python (минуя VLOOKUP)
    # VLOOKUP($A$1, Таблица!$B:$I, COLUMN(), FALSE) не работает, т.к. match_id
    # отсутствует в столбце B таблицы. Заполняем значения напрямую.
    _populate_incognito_data(store, overall_rows, match.home, match.away, home_rows, away_rows)

    # M26-M28: rates хозяев из home таблицы (M = col 13)
    # 1PR стратегия (#8) читает: Анализ!H24=Расчеты!M26, J24=M28, K24=M27
    if home_rows:
        home_team_row = _find_team_in_table(home_rows, match.home)
        if home_team_row:
            rates = _team_rates(home_team_row)
            if rates:
                for row_num, rate in zip((26, 27, 28), rates):
                    store.set_value(SHEET_CALC, f"{_col(13)}{row_num}", rate)  # M col on Расчеты

    # M30-M32: rates гостей из away таблицы (M = col 13, для 5Match в Анализ!H26/J26/K26)
    # 5Match стратегия (#5) читает: Анализ!H26=Расчеты!M30, J26=M31, K26=M32
    if away_rows:
        away_team_row = _find_team_in_table(away_rows, match.away)
        if away_team_row:
            rates = _team_rates(away_team_row)
            if rates:
                for row_num, rate in zip((30, 31, 32), rates):
                    store.set_value(SHEET_CALC, f"{_col(13)}{row_num}", rate)  # M col on Расчеты

    for attr, col in (
        ("form_overall", 1),
        ("form_home", 11),
        ("form_away", 21),
    ):
        rows = _table_rows(getattr(payload, attr))
        if rows:
            store.set_range(SHEET_FORM, 2, col, rows)

    store.set_value(SHEET_CALC, "A1", match.match_id)

    if match.league:
        store.set_value(SHEET_ANALYSIS, "E2", match.league)
    if match.date:
        store.set_value(SHEET_ANALYSIS, "K2", match.date)
    if match.home:
        store.set_value(SHEET_ANALYSIS, "E3", match.home)
    if match.away:
        store.set_value(SHEET_ANALYSIS, "K3", match.away)


def apply_settings_to_store(store: CellStore, sport: int, source: int = 2) -> None:
    from settings import calc_sport_id

    store.set_value(SHEET_START, "R2", calc_sport_id(int(sport or 1)))
    store.set_value(SHEET_START, "X2", source)


def apply_list_odds_to_store(
    store: CellStore,
    current_home: float,
    current_draw: float,
    current_away: float,
) -> None:
    if current_home:
        store.set_value(SHEET_ANALYSIS, "B15", current_home)
    if current_draw:
        store.set_value(SHEET_ANALYSIS, "C15", current_draw)
    if current_away:
        store.set_value(SHEET_ANALYSIS, "D15", current_away)


def apply_odds_to_store(store: CellStore, odds: OddsSheetData) -> None:
    store.set_value(SHEET_ODDS, "A1", "HOME_ID")
    store.set_value(SHEET_ODDS, "B1", "AWAY_ID")
    store.set_value(SHEET_ODDS, "A2", odds.home_id)
    store.set_value(SHEET_ODDS, "B2", odds.away_id)

    start_col = 3
    row = 3
    for bk in odds.bookmakers:
        store.set_value(SHEET_ODDS, f"{_col(start_col)}1", f"БК_{bk.bookmaker_id}")
        store.set_value(SHEET_ODDS, f"{_col(start_col)}2", "Рынок")
        store.set_value(SHEET_ODDS, f"{_col(start_col + 1)}2", "Нач")
        store.set_value(SHEET_ODDS, f"{_col(start_col + 2)}2", "Тек")
        r = row
        for market in bk.markets.values():
            store.set_value(SHEET_ODDS, f"{_col(start_col)}{r}", market.market_name)
            if market.opening is not None:
                store.set_value(SHEET_ODDS, f"{_col(start_col + 1)}{r}", market.opening)
            if market.current is not None:
                store.set_value(SHEET_ODDS, f"{_col(start_col + 2)}{r}", market.current)
            r += 1
        start_col += 3


def _col(n: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(n)


def apply_queued_odds(
    store: CellStore,
    list_odds: Optional[Tuple[float, float, float]],
) -> None:
    if list_odds:
        apply_list_odds_to_store(store, *list_odds)
