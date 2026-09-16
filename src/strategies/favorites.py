"""Стратегия Favorites (#5): победа фаворита в оптимальном диапазоне кф."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

from db import get_db_connection
from src.strategies.base import MatchContext, Strategy, StrategySignal
from favorites_stats.missing_players_api import side_injury_totals
from favorites_stats.settlement import identify_favorite
from favorites_stats.storage import load_missing_players
from favorites_stats.thresholds import load_win_ranges, odds_in_range

FAVORITES_STRATEGY_ID = 5


def _env_bool(name: str, default: bool = True) -> bool:
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ("1", "true", "yes")


def max_1x2_odds(odds_data) -> Tuple[float, float]:
    home_best = away_best = 0.0
    for bk in getattr(odds_data, "bookmakers", []) or []:
        m1 = bk.markets.get("1X2_1")
        m2 = bk.markets.get("1X2_2")
        if m1 and m1.current:
            home_best = max(home_best, float(m1.current))
        if m2 and m2.current:
            away_best = max(away_best, float(m2.current))
    return home_best, away_best


def _favorite_has_confirmed_injury(match_id: str, favorite_side: str) -> bool:
    with get_db_connection() as conn:
        players = load_missing_players(conn, match_id)
    if not players:
        return False
    fav_side = "HOME" if favorite_side == "home" else "AWAY"
    return side_injury_totals(players, fav_side)["confirmed_injuries"] > 0


def compute_favorites_win_prediction(
    match_id: str,
    sport: int,
    *,
    odds_data=None,
    odds_home: Optional[float] = None,
    odds_away: Optional[float] = None,
    skip_injured_favorite: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Сигнал «1»/«2» — победа фаворита при кф в оптимальном диапазоне."""
    sport_id = int(sport or 1)
    band = load_win_ranges().get(sport_id)
    if not band:
        return None

    if odds_home is None or odds_away is None:
        if not odds_data:
            return None
        odds_home, odds_away = max_1x2_odds(odds_data)

    fav = identify_favorite(odds_home, odds_away)
    if not fav:
        return None

    odds_min, odds_max = band
    if not odds_in_range(fav.win_odds, odds_min, odds_max):
        return None

    if skip_injured_favorite is None:
        skip_injured_favorite = _env_bool("DELUX_FAV_SKIP_INJURED", True)
    if skip_injured_favorite and _favorite_has_confirmed_injury(match_id, fav.side):
        return None

    prediction = "1" if fav.side == "home" else "2"
    label = "П1" if prediction == "1" else "П2"
    return {
        "prediction": prediction,
        "label": label,
        "odds": fav.win_odds,
        "favorite_side": fav.side,
        "odds_range": {"min": odds_min, "max": odds_max},
        "notes": json.dumps(
            {
                "sport": sport_id,
                "favorite_side": fav.side,
                "win_odds": fav.win_odds,
                "odds_range": {"min": odds_min, "max": odds_max},
                "underdog_odds": fav.underdog_odds,
            },
            ensure_ascii=False,
        ),
    }


class FavoritesStrategy(Strategy):
    id = FAVORITES_STRATEGY_ID
    name = "Favorites"
    description = "Победа фаворита — оптимальный диапазон кф"

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        extra = ctx.extra or {}
        data = compute_favorites_win_prediction(
            ctx.match_id,
            ctx.sport,
            odds_data=ctx.odds_data,
            odds_home=extra.get("odds_home"),
            odds_away=extra.get("odds_away"),
        )
        return StrategySignal.from_dict(data)
