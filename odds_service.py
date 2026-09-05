"""Загрузка и разбор коэффициентов без Excel (порт odds_fetch + Module3)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from flashscore_feed import map_odds_params
from odds_normalize import canonicalize_market, split_canonical, to_float as _to_float

API_BASE = "https://global.ds.lsapp.eu/odds/pq_graphql"
API_HEADERS = {
    "Accept": "application/json",
    "X-Fsign": "SW9D1eZo",
}

ODDS_BK_COLS = 3
ODDS_BK_TITLE_ROW = 1
ODDS_SUBHEADER_ROW = 2
ODDS_DATA_START_ROW = 3
ODDS_FIRST_BK_COL = 3
STATIC_MARKETS = ["1X2_1", "1X2_X", "1X2_2", "BTTS_YES", "BTTS_NO", "DC_1X", "DC_12", "DC_X2"]


@dataclass
class MarketOdds:
    market_name: str
    opening: Optional[float] = None
    current: Optional[float] = None


@dataclass
class BookmakerOdds:
    bookmaker_id: int
    markets: Dict[str, MarketOdds] = field(default_factory=dict)


@dataclass
class OddsSheetData:
    home_id: str
    away_id: str
    bookmakers: List[BookmakerOdds] = field(default_factory=list)

    def all_markets_flat(self) -> List[Dict]:
        rows: List[Dict] = []
        for bk in self.bookmakers:
            for market in bk.markets.values():
                if market.current is None:
                    continue
                canon = canonicalize_market(market.market_name) or market.market_name
                meta = split_canonical(canon)
                rows.append(
                    {
                        "market_name": canon,
                        "odds_value": market.current,
                        "outcome": meta.get("outcome"),
                        "side": meta.get("side"),
                        "line_value": meta.get("line_value")
                        if meta.get("line_value") is not None
                        else _parse_line_value(canon),
                    }
                )
        return rows


def _parse_line_value(market_name: str) -> Optional[float]:
    for prefix in ("OVER ", "UNDER ", "HANDICAP HOME ", "HANDICAP AWAY ", "1st Half OVER ", "1st Half UNDER "):
        if market_name.upper().startswith(prefix.upper()):
            tail = market_name[len(prefix) :].strip()
            try:
                return float(tail.replace(",", "."))
            except ValueError:
                return None
    return None


def api_request(
    event_id: str,
    project_id: str,
    geo_ip_code: str,
    geo_ip_subdivision_code: str,
) -> dict:
    params = {
        "_hash": "oce",
        "eventId": event_id,
        "projectId": project_id,
        "geoIpCode": geo_ip_code,
        "geoIpSubdivisionCode": geo_ip_subdivision_code,
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=API_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def fetch_odds_data(event_id: str, source_value) -> Tuple[Optional[dict], List[dict]]:
    for project_id, geo_code, geo_sub in map_odds_params(source_value):
        data = api_request(event_id, project_id, geo_code, geo_sub)
        odds_groups = data.get("data", {}).get("findOddsByEventId", {}).get("odds", [])
        if odds_groups:
            return data, odds_groups
    return None, []


def has_participant(odd: dict) -> bool:
    return "eventParticipantId" in odd and odd["eventParticipantId"] not in (None, "")


def participant_match(odd: dict, participant_id: str) -> bool:
    return str(odd.get("eventParticipantId", "")) == str(participant_id)


def is_active(odd: dict) -> bool:
    if "active" not in odd:
        return True
    return bool(odd.get("active"))


def safe_num(v):
    return _to_float(v)


def extract_participants(odds_groups: list) -> Tuple[str, str]:
    home_id = ""
    away_id = ""
    for g in odds_groups:
        for odd in g.get("odds", []):
            pid = odd.get("eventParticipantId")
            if pid in (None, ""):
                continue
            if home_id == "":
                home_id = str(pid)
            elif away_id == "" and str(pid) != home_id:
                away_id = str(pid)
                return home_id, away_id
    return home_id, away_id


class _OddsBuilder:
    def __init__(self, home_id: str, away_id: str):
        self.home_id = home_id
        self.away_id = away_id
        self.bookmakers: Dict[int, BookmakerOdds] = {}
        self._next_row: Dict[int, int] = {}

    def _bk(self, bookmaker_id: int) -> BookmakerOdds:
        if bookmaker_id not in self.bookmakers:
            bk = BookmakerOdds(bookmaker_id=bookmaker_id)
            for market in STATIC_MARKETS:
                bk.markets[market.upper()] = MarketOdds(market_name=market)
            self.bookmakers[bookmaker_id] = bk
            self._next_row[bookmaker_id] = ODDS_DATA_START_ROW + len(STATIC_MARKETS)
        return self.bookmakers[bookmaker_id]

    def write_market(self, bookmaker_id: int, market_name: str, opening, current):
        name = (market_name or "").strip()
        if not name:
            return
        key = name.upper()
        bk = self._bk(bookmaker_id)
        if key not in bk.markets:
            bk.markets[key] = MarketOdds(market_name=name)
        market = bk.markets[key]
        o = safe_num(opening)
        c = safe_num(current)
        if o is not None:
            market.opening = o
        if c is not None:
            market.current = c

    def build(self) -> OddsSheetData:
        return OddsSheetData(
            home_id=self.home_id,
            away_id=self.away_id,
            bookmakers=list(self.bookmakers.values()),
        )


def parse_groups_for_bookmaker(
    groups: list,
    builder: _OddsBuilder,
    bookmaker_id: int,
    home_id: str,
    away_id: str,
) -> None:
    for g in groups:
        betting_type = g.get("bettingType")
        scope = g.get("bettingScope")
        odds = g.get("odds", [])

        if betting_type == "HOME_DRAW_AWAY" and scope == "FULL_TIME":
            for odd in odds:
                if not is_active(odd):
                    continue
                if participant_match(odd, home_id):
                    builder.write_market(bookmaker_id, "1X2_1", odd.get("opening"), odd.get("value"))
                elif participant_match(odd, away_id):
                    builder.write_market(bookmaker_id, "1X2_2", odd.get("opening"), odd.get("value"))
                elif not has_participant(odd):
                    builder.write_market(bookmaker_id, "1X2_X", odd.get("opening"), odd.get("value"))

        elif betting_type == "HOME_AWAY" and scope == "FULL_TIME_OVER_TIME":
            for odd in odds:
                if not is_active(odd):
                    continue
                if participant_match(odd, home_id):
                    builder.write_market(bookmaker_id, "1X2_1", odd.get("opening"), odd.get("value"))
                elif participant_match(odd, away_id):
                    builder.write_market(bookmaker_id, "1X2_2", odd.get("opening"), odd.get("value"))

        elif betting_type == "BOTH_TEAMS_TO_SCORE" and scope == "FULL_TIME":
            for odd in odds:
                btts = str(odd.get("bothTeamsToScore", "")).lower()
                if btts == "true":
                    builder.write_market(bookmaker_id, "BTTS_YES", odd.get("opening"), odd.get("value"))
                elif btts == "false":
                    builder.write_market(bookmaker_id, "BTTS_NO", odd.get("opening"), odd.get("value"))

        elif betting_type == "DOUBLE_CHANCE" and scope == "FULL_TIME":
            for odd in odds:
                if participant_match(odd, home_id):
                    builder.write_market(bookmaker_id, "DC_1X", odd.get("opening"), odd.get("value"))
                elif participant_match(odd, away_id):
                    builder.write_market(bookmaker_id, "DC_X2", odd.get("opening"), odd.get("value"))
                elif not has_participant(odd):
                    builder.write_market(bookmaker_id, "DC_12", odd.get("opening"), odd.get("value"))

        elif betting_type == "OVER_UNDER" and scope in ("FULL_TIME", "FIRST_PERIOD"):
            prefix = "1st Half " if scope == "FIRST_PERIOD" else ""
            lines = defaultdict(dict)
            for odd in odds:
                handicap = str((odd.get("handicap") or {}).get("value", "")).strip()
                if not handicap:
                    continue
                sel = str(odd.get("selection", "")).upper()
                if sel == "OVER":
                    lines[handicap]["over_open"] = odd.get("opening")
                    lines[handicap]["over_value"] = odd.get("value")
                elif sel == "UNDER":
                    lines[handicap]["under_open"] = odd.get("opening")
                    lines[handicap]["under_value"] = odd.get("value")
            for line_val, data in lines.items():
                builder.write_market(
                    bookmaker_id,
                    f"{prefix}OVER {line_val}",
                    data.get("over_open"),
                    data.get("over_value"),
                )
                builder.write_market(
                    bookmaker_id,
                    f"{prefix}UNDER {line_val}",
                    data.get("under_open"),
                    data.get("under_value"),
                )

        elif betting_type == "ASIAN_HANDICAP" and scope == "FULL_TIME":
            for odd in odds:
                handicap = str((odd.get("handicap") or {}).get("value", "")).strip()
                if not handicap:
                    continue
                if participant_match(odd, home_id):
                    builder.write_market(
                        bookmaker_id,
                        f"HANDICAP HOME {handicap}",
                        odd.get("opening"),
                        odd.get("value"),
                    )
                elif participant_match(odd, away_id):
                    builder.write_market(
                        bookmaker_id,
                        f"HANDICAP AWAY {handicap}",
                        odd.get("opening"),
                        odd.get("value"),
                    )


def build_fallback_odds(event_id: str) -> Optional[OddsSheetData]:
    """Минимальные данные для расчёта, если pq_graphql не вернул линию БК."""
    from analysis_data import fetch_match_page_ids

    home_id, away_id, _, _ = fetch_match_page_ids(event_id)
    if not home_id or not away_id:
        return None
    return OddsSheetData(home_id=home_id, away_id=away_id, bookmakers=[])


def load_odds(event_id: str, source_value) -> Tuple[int, Optional[OddsSheetData]]:
    """Коды: 0=OK, 2=нет кф, 3=нет участников."""
    _data, odds_groups = fetch_odds_data(event_id, source_value)
    if not odds_groups:
        return 2, None

    home_id, away_id = extract_participants(odds_groups)
    if not home_id or not away_id:
        return 3, None

    builder = _OddsBuilder(home_id, away_id)
    bookmaker_ids: List[int] = []
    seen = set()
    for g in odds_groups:
        bk = g.get("bookmakerId")
        if bk not in seen:
            seen.add(bk)
            bookmaker_ids.append(bk)

    for bk in bookmaker_ids:
        groups = [g for g in odds_groups if g.get("bookmakerId") == bk]
        parse_groups_for_bookmaker(groups, builder, bk, home_id, away_id)

    return 0, builder.build()


class OddsExcelWriter:
    """Запись OddsSheetData на лист «Коэффициенты» (только для calc-движка)."""

    def __init__(self, ws_odds):
        self.ws = ws_odds

    def clear_sheet(self):
        last_col = self.ws.Cells(ODDS_BK_TITLE_ROW, self.ws.Columns.Count).End(-4159).Column
        last_row = self.ws.Cells(self.ws.Rows.Count, 1).End(-4162).Row
        if last_row < ODDS_DATA_START_ROW:
            last_row = ODDS_DATA_START_ROW + 200
        if last_col > 1:
            self.ws.Range(self.ws.Cells(1, 1), self.ws.Cells(last_row, last_col)).ClearContents()

    def write(self, data: OddsSheetData) -> None:
        self.clear_sheet()
        self.ws.Range("A1").Value = "HOME_ID"
        self.ws.Range("B1").Value = "AWAY_ID"
        self.ws.Range("A2").Value = data.home_id
        self.ws.Range("B2").Value = data.away_id

        start_col = ODDS_FIRST_BK_COL
        for bk in data.bookmakers:
            self.ws.Cells(ODDS_BK_TITLE_ROW, start_col).Value = f"БК_{bk.bookmaker_id}"
            self.ws.Cells(ODDS_SUBHEADER_ROW, start_col).Value = "Рынок"
            self.ws.Cells(ODDS_SUBHEADER_ROW, start_col + 1).Value = "Нач"
            self.ws.Cells(ODDS_SUBHEADER_ROW, start_col + 2).Value = "Тек"

            row = ODDS_DATA_START_ROW
            for market in bk.markets.values():
                self.ws.Cells(row, start_col).Value = market.market_name
                if market.opening is not None:
                    self.ws.Cells(row, start_col + 1).Value = market.opening
                if market.current is not None:
                    self.ws.Cells(row, start_col + 2).Value = market.current
                row += 1
            start_col += ODDS_BK_COLS
