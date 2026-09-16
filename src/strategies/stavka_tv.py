"""Стратегия StavkaTV (#6): прогнозы tipster'ов stavka.tv."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.strategies.base import MatchContext, Strategy, StrategySignal

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

SPORT_ALIASES = {
    1: {"soccer", "football", "футбол"},
    3: {"basketball", "баскетбол"},
    4: {"ice-hockey", "hockey", "хоккей", "ice hockey"},
    6: {"baseball", "бейсбол"},
}

_TEAM_SUFFIXES = (
    " москва",
    " санкт-петербург",
    " петербург",
    " спб",
)

_SKIP_OUTCOME = (
    "желт",
    "карт",
    "угл",
    "фора",
    "handicap",
    "индивидуальн",
    "тайм",
    "четверт",
    "период",
    "сет ",
    " по сетам",
)


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


def _core_team(name: str) -> str:
    n = _norm_team(name)
    for sfx in _TEAM_SUFFIXES:
        if n.endswith(sfx):
            return n[: -len(sfx)].strip()
    return n


def teams_match(left: str, right: str) -> bool:
    a, b = _norm_team(left), _norm_team(right)
    if not a or not b:
        return False
    if a == b:
        return True
    ca, cb = _core_team(left), _core_team(right)
    return bool(ca) and ca == cb and len(ca) >= 3


def _sport_ok(row_sport: Any, delux_sport: int) -> bool:
    raw = str(row_sport or "").strip().casefold()
    if not raw:
        return True
    aliases = SPORT_ALIASES.get(int(delux_sport or 1), set())
    return raw in aliases or raw == DELUX_SPORT_TO_STAVKA.get(int(delux_sport or 1), "")


def _row_orientation(home: str, away: str, row: dict) -> Optional[str]:
    rh, ra = row.get("home_team") or "", row.get("away_team") or ""
    if teams_match(home, rh) and teams_match(away, ra):
        return "same"
    if teams_match(home, ra) and teams_match(away, rh):
        return "swap"
    return None


def _flip_prediction(pred: str) -> str:
    if pred == "1":
        return "2"
    if pred == "2":
        return "1"
    return pred


def map_stavka_to_delux(outcome: str, bet_type: str) -> Optional[str]:
    outcome = (outcome or "").strip()
    bt = (bet_type or "").strip().lower()
    ol = outcome.lower()

    if any(m in ol for m in _SKIP_OUTCOME):
        return None

    if bt == "home_win" or re.search(r"победа\s*1\b", ol):
        return "1"
    if bt == "away_win" or re.search(r"победа\s*2\b", ol):
        return "2"
    if bt == "btts" or "обе забьют" in ol:
        return "ОЗ"
    if "ничья" in ol or bt == "draw":
        return "X"

    m = re.search(r"(тб|over|больше)\s*\(?\s*([0-9]+(?:[.,][0-9]+)?)", ol, re.I)
    if m:
        return f"ТБ{m.group(2).replace(',', '.')}"
    if bt == "total_over":
        return "ТБ"

    m = re.search(r"(тм|under|меньше)\s*\(?\s*([0-9]+(?:[.,][0-9]+)?)", ol, re.I)
    if m:
        return f"ТМ{m.group(2).replace(',', '.')}"
    if bt == "total_under":
        return "ТМ"

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

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, predictor_slug, predictor_name, home_team, away_team, sport,
                   outcome, bet_type, rate, comment, match_url, match_date, match_time, status
            FROM predictions
            WHERE (? = '' OR status = ? OR status IS NULL OR TRIM(COALESCE(status, '')) = '')
            """,
            (status, status),
        ).fetchall()
    finally:
        conn.close()

    matched: List[dict] = []
    for raw in rows:
        row = dict(raw)
        if not _sport_ok(row.get("sport"), sport):
            continue
        orient = _row_orientation(home, away, row)
        if not orient:
            continue
        row["_orientation"] = orient
        matched.append(row)

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
    chosen = None
    prediction = None
    for pick in picks:
        mapped = map_stavka_to_delux(pick.get("outcome", ""), pick.get("bet_type", ""))
        if not mapped:
            continue
        if pick.get("_orientation") == "swap":
            mapped = _flip_prediction(mapped)
        chosen = pick
        prediction = mapped
        break
    if not chosen or not prediction:
        return None

    rate = chosen.get("rate")
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
                "predictor_slug": chosen.get("predictor_slug"),
                "predictor_name": chosen.get("predictor_name"),
                "outcome": chosen.get("outcome"),
                "bet_type": chosen.get("bet_type"),
                "comment": chosen.get("comment"),
                "match_url": chosen.get("match_url"),
                "match_date": chosen.get("match_date"),
                "match_time": chosen.get("match_time"),
                "orientation": chosen.get("_orientation"),
                "picks_found": len(picks),
            },
            ensure_ascii=False,
        ),
    }


class StavkaTvStrategy(Strategy):
    id = STAVKA_TV_STRATEGY_ID
    name = "StavkaTV"
    description = "Прогнозы tipster'ов stavka.tv"

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        data = compute_stavka_tv_prediction(
            ctx.match_id,
            ctx.home,
            ctx.away,
            ctx.sport,
        )
        return StrategySignal.from_dict(data)
