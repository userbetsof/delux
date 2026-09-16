"""Стратегия 1pr (#8): исход с макс. вероятностью подстратегии «1 пр»."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, Optional

from db import get_database_path, get_db_connection
from src.strategies.base import MatchContext, Strategy, StrategySignal

ONEPR_STRATEGY_ID = 8
ONEPR_SUB_STRATEGY_NAME = "1 пр"
LABEL_MAP = {"1": "П1", "X": "X", "2": "П2"}


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(str(value).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None


def _devig(odds: Dict[str, Optional[float]]) -> Dict[str, float]:
    inv = {k: 1.0 / o for k, o in odds.items() if o and o > 1}
    total = sum(inv.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in inv.items()}


def _resolve_onepr_sub_id(conn: sqlite3.Connection) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM sub_strategies WHERE strategy_name = ? LIMIT 1",
        (ONEPR_SUB_STRATEGY_NAME,),
    ).fetchone()
    return int(row[0]) if row else None


def _load_1x2_odds(conn: sqlite3.Connection, match_id: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in conn.execute(
        """
        SELECT market_name, odds_value
        FROM odds
        WHERE match_id = ?
          AND UPPER(market_name) IN ('1X2_1', '1X2_X', '1X2_2')
          AND odds_value IS NOT NULL
        """,
        (match_id,),
    ):
        odds = _to_float(row[1] if not isinstance(row, sqlite3.Row) else row["odds_value"])
        if not odds or odds <= 1:
            continue
        key = str(row[0] if not isinstance(row, sqlite3.Row) else row["market_name"]).upper()
        if key not in out or odds > out[key]:
            out[key] = odds
    return out


def compute_onepr_prediction(
    match_id: str,
    *,
    use_devig: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """
    Берёт вероятности «1 пр», выбирает исход с макс. p, кф 1X2.
    prediction: '1' / 'X' / '2'
    """
    if use_devig is None:
        use_devig = os.environ.get("ONEPR_USE_DEVIG", "true").strip().lower() in (
            "1",
            "true",
            "yes",
        )

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        sid = _resolve_onepr_sub_id(conn)
        if sid is None:
            return None
        row = conn.execute(
            """
            SELECT home_win_prob, draw_prob, away_win_prob
            FROM outcome_probabilities
            WHERE match_id = ? AND strategy_id = ?
            LIMIT 1
            """,
            (match_id, sid),
        ).fetchone()
        if not row:
            return None
        probs = {
            "1": float(row["home_win_prob"] or 0) / 100.0,
            "X": float(row["draw_prob"] or 0) / 100.0,
            "2": float(row["away_win_prob"] or 0) / 100.0,
        }
        if sum(probs.values()) < 0.05:
            return None

        odds_raw = _load_1x2_odds(conn, match_id)

    odds_map = {
        "1": odds_raw.get("1X2_1"),
        "X": odds_raw.get("1X2_X"),
        "2": odds_raw.get("1X2_2"),
    }
    sel = max(probs, key=probs.get)
    p = probs[sel]
    selected_odds = odds_map.get(sel)
    if not selected_odds or selected_odds <= 1:
        return None

    if use_devig:
        implied_map = _devig(odds_map)
        implied = implied_map.get(sel, 1.0 / selected_odds)
    else:
        implied = 1.0 / selected_odds
    edge = p - implied

    return {
        "prediction": sel,
        "label": LABEL_MAP[sel],
        "odds": float(selected_odds),
        "probability": round(p, 6),
        "difference": round(edge, 6),
        "notes": json.dumps(
            {
                "source": "1pr",
                "sub_strategy": ONEPR_SUB_STRATEGY_NAME,
                "label": LABEL_MAP[sel],
                "home_probability": round(probs["1"], 6),
                "draw_probability": round(probs["X"], 6),
                "away_probability": round(probs["2"], 6),
                "home_odds": odds_map.get("1"),
                "draw_odds": odds_map.get("X"),
                "away_odds": odds_map.get("2"),
                "selected_odds": float(selected_odds),
                "difference": round(edge, 6),
                "use_devig": use_devig,
            },
            ensure_ascii=False,
        ),
    }


def save_onepr_strategy_prediction(match_id: str) -> Optional[Dict[str, Any]]:
    """Рассчитать и записать в strategy_predictions (id=8)."""
    from db import upsert_strategy_prediction

    pred = compute_onepr_prediction(match_id)
    if not pred:
        return None
    upsert_strategy_prediction(
        match_id,
        ONEPR_STRATEGY_ID,
        pred["prediction"],
        odds=pred.get("odds"),
        notes=pred.get("notes"),
    )
    return pred


class OneprStrategy(Strategy):
    id = ONEPR_STRATEGY_ID
    name = "1pr"
    description = "Исход с макс. вероятностью подстратегии «1 пр»"

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        data = compute_onepr_prediction(ctx.match_id)
        return StrategySignal.from_dict(data)
