"""Стратегия StavkaTV (#6): прогнозы tipster'ов stavka.tv."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

STAVKA_TV_STRATEGY_ID = 6

DEFAULT_STAVKA_DB = Path(r"C:\papki\work\bets\stavka_tw\predictions.db")

PREDICTOR_PRIORITY = (
    "yuriy-teslenok",
    "aleksandr-lyagin",
    "mikhail-dao",
    "jack07",
)

DELUX_SPORT_TO_STAVKA = {
    1: "soccer",
    3: "basketball",
    4: "ice-hockey",
    6: "baseball",
}


def stavka_db_path(explicit: Optional[str] = None) -> Path:
    raw = (explicit or os.environ.get("STAVKA_TW_DB") or os.environ.get("STAVKA_TW_ROOT", "")).strip()
    if raw:
        path = Path(raw)
        if path.is_dir():
            return path / "predictions.db"
        return path
    return DEFAULT_STAVKA_DB


def _norm_team(name: str) -> str:
    text = (name or "").strip().casefold()
    return re.sub(r"\s+", " ", text)


def map_stavka_to_delux(outcome: str, bet_type: str) -> Optional[str]:
    outcome = (outcome or "").strip()
    bt = (bet_type or "").strip().lower()
    ol = outcome.lower()

    if bt == "home_win" or "победа 1" in ol:
        return "1"
    if bt == "away_win" or "победа 2" in ol:
        return "2"
    if bt == "btts" or "обе забьют" in ol:
        return "ОЗ"
    if "ничья" in ol or bt == "draw":
        return "X"

    m = re.search(r"(тб|over|больше)\s*([0-9]+(?:[.,][0-9]+)?)", ol, re.I)
    if m or bt == "total_over":
        line = m.group(2).replace(",", ".") if m else ""
        return f"ТБ{line}" if line else "ТБ"

    m = re.search(r"(тм|under|меньше)\s*([0-9]+(?:[.,][0-9]+)?)", ol, re.I)
    if m or bt == "total_under":
        line = m.group(2).replace(",", ".") if m else ""
        return f"ТМ{line}" if line else "ТМ"

    if bt in ("handicap", "individual_total", "corners", "other", "unknown", "win", "total"):
        return None
    if outcome and len(outcome) <= 20:
        return outcome
    return None


def find_stavka_predictions(
    home: str,
    away: str,
    *,
    sport: int = 1,
    status: str = "upcoming",
    db_path: Optional[str] = None,
) -> List[dict]:
    path = stavka_db_path(db_path)
    if not path.is_file():
        return []

    stavka_sport = DELUX_SPORT_TO_STAVKA.get(int(sport or 1))
    if not stavka_sport:
        return []

    nh, na = _norm_team(home), _norm_team(away)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, predictor_slug, predictor_name, home_team, away_team, sport,
                   outcome, bet_type, rate, comment, match_url, match_date, match_time, status
            FROM predictions
            WHERE status = ? AND sport = ?
            """,
            (status, stavka_sport),
        ).fetchall()
    finally:
        conn.close()

    matched = [
        dict(row)
        for row in rows
        if _norm_team(row["home_team"]) == nh and _norm_team(row["away_team"]) == na
    ]
    priority = {slug: idx for idx, slug in enumerate(PREDICTOR_PRIORITY)}
    matched.sort(key=lambda r: priority.get(r.get("predictor_slug", ""), 999))
    return matched


def compute_stavka_tv_prediction(
    match_id: str,
    home: str,
    away: str,
    sport: int,
    *,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    picks = find_stavka_predictions(home, away, sport=sport, db_path=db_path)
    if not picks:
        return None

    pick = picks[0]
    prediction = map_stavka_to_delux(pick.get("outcome", ""), pick.get("bet_type", ""))
    if not prediction:
        return None

    rate = pick.get("rate")
    try:
        odds = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        odds = None

    return {
        "prediction": prediction,
        "odds": odds,
        "notes": json.dumps(
            {
                "source": "stavka_tv",
                "predictor_slug": pick.get("predictor_slug"),
                "predictor_name": pick.get("predictor_name"),
                "outcome": pick.get("outcome"),
                "bet_type": pick.get("bet_type"),
                "comment": pick.get("comment"),
                "match_url": pick.get("match_url"),
                "match_date": pick.get("match_date"),
                "match_time": pick.get("match_time"),
                "picks_found": len(picks),
            },
            ensure_ascii=False,
        ),
    }
