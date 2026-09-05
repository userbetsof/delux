"""Оптимальные диапазоны кф победы фаворита (из backtest)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "data" / "favorites_stats_report.json"

DEFAULT_WIN_RANGES: Dict[int, Tuple[float, float]] = {
    1: (2.3, 4.0),
    6: (1.8, 1.8),
}

MIN_RANGE_BETS = 30


def load_win_ranges(report_path: Optional[Path] = None) -> Dict[int, Tuple[float, float]]:
    path = report_path or DEFAULT_REPORT
    ranges = dict(DEFAULT_WIN_RANGES)
    if not path.is_file():
        return ranges

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ranges

    for sport in report.get("backtest", {}).get("by_sport", []):
        sport_id = int(sport.get("sport_id") or 0)
        optimal = sport.get("optimal_win_odds_range")
        if not optimal or not sport_id:
            continue
        bets = int(optimal.get("bets") or 0)
        if bets < MIN_RANGE_BETS:
            continue
        ranges[sport_id] = (float(optimal["odds_min"]), float(optimal["odds_max"]))

    return ranges


def odds_in_range(odds: float, odds_min: float, odds_max: float) -> bool:
    return odds_min - 1e-9 <= odds <= odds_max + 1e-9
