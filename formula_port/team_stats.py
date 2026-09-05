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
    "Дата/Время",
    "Дома",
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


def _h2h_rows(matches: List[HistoryMatch]) -> List[List]:
    return [
        [m.tour_name, m.date, m.home_name, m.away_name, m.home_ht, m.away_ht]
        for m in matches
    ]


def _table_rows(rows: List[TableRow]) -> List[List]:
    return [
        [r.rank, r.team, r.played, r.wins, r.draws, r.losses, r.scored, r.conceded, r.points]
        for r in rows
    ]


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

    for attr, col in (
        ("table_overall", 1),
        ("table_home", 11),
        ("table_away", 21),
    ):
        rows = _table_rows(getattr(payload, attr))
        if rows:
            store.set_range(SHEET_TABLE, 2, col, rows)

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
