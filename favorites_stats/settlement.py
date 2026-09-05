"""Определение фаворита и расчёт исходов ставок."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


HANDICAP_RE = re.compile(r"^HANDICAP\s+(HOME|AWAY)\s+([-+]?\d+(?:\.\d+)?)$", re.I)


@dataclass
class FavoriteInfo:
    side: str  # "home" | "away"
    win_odds: float
    underdog_odds: float


def identify_favorite(odds_home: Optional[float], odds_away: Optional[float]) -> Optional[FavoriteInfo]:
    """Меньший кф 1X2 — фаворит; при равенстве или отсутствии данных — None."""
    if not odds_home or not odds_away or odds_home <= 1 or odds_away <= 1:
        return None
    if abs(odds_home - odds_away) < 1e-9:
        return None
    if odds_home < odds_away:
        return FavoriteInfo(side="home", win_odds=odds_home, underdog_odds=odds_away)
    return FavoriteInfo(side="away", win_odds=odds_away, underdog_odds=odds_home)


def settle_win(home_score: int, away_score: int, favorite_side: str) -> bool:
    if favorite_side == "home":
        return home_score > away_score
    return away_score > home_score


def parse_handicap_market(market_name: str) -> Optional[Tuple[str, float]]:
    m = HANDICAP_RE.match((market_name or "").strip())
    if not m:
        return None
    side = m.group(1).lower()
    try:
        line = float(m.group(2))
    except ValueError:
        return None
    return side, line


def is_favorite_handicap_line(line_side: str, favorite_side: str, line_value: float) -> bool:
    """Линия на отрицательную фору фаворита."""
    if line_side == favorite_side and line_value < 0:
        return True
    if favorite_side == "home" and line_side == "home" and line_value < 0:
        return True
    if favorite_side == "away" and line_side == "away" and line_value < 0:
        return True
    return False


def settle_handicap(
    home_score: int,
    away_score: int,
    line_side: str,
    line_value: float,
) -> Optional[bool]:
    """
    Победа по форе: очки стороны + фора > соперник.
    None — push (ровно).
    """
    if line_side == "home":
        adjusted = home_score + line_value
        if abs(adjusted - away_score) < 1e-9:
            return None
        return adjusted > away_score
    adjusted = away_score + line_value
    if abs(adjusted - home_score) < 1e-9:
        return None
    return adjusted > home_score


def profit_for_result(won: Optional[bool], odds: float, stake: float = 1.0) -> float:
    if won is None:
        return 0.0
    return (odds * stake - stake) if won else -stake


def favorite_handicap_lines(
    odds_by_market: Dict[str, float],
    favorite_side: str,
) -> List[Dict[str, Any]]:
    """Все линии форы фаворита из словаря рынков."""
    lines: List[Dict[str, Any]] = []
    for market, odds in odds_by_market.items():
        parsed = parse_handicap_market(market)
        if not parsed or odds <= 1:
            continue
        side, line_value = parsed
        if not is_favorite_handicap_line(side, favorite_side, line_value):
            continue
        lines.append(
            {
                "market_name": market,
                "side": side,
                "handicap_value": line_value,
                "odds": float(odds),
            }
        )
    return lines


def select_handicap_bet_line(lines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Стратегия из проекта favorites: макс. кф среди линий фаворита,
    ставка — наибольший кф строго ниже максимума (или макс., если ниже нет).
    """
    if not lines:
        return None
    max_odds = max(l["odds"] for l in lines)
    below = [l for l in lines if l["odds"] < max_odds - 1e-9]
    bet_line = max(below, key=lambda x: x["odds"]) if below else max(lines, key=lambda x: x["odds"])
    return {
        **bet_line,
        "max_odds": max_odds,
        "bet_odds": bet_line["odds"],
    }
