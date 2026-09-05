"""Стратегия BTS (id=4): обе забьют при очных 2/2 в последних 5 играх."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from analysis_data import MatchSettings
from flashscore_feed import fetch_feed

BTS_STRATEGY_ID = 4
BTS_PREDICTION = "ОЗ"


@dataclass
class _H2HGame:
    date: datetime
    home_score: int
    away_score: int


def _parse_h2h_block(data: str) -> List[_H2HGame]:
    games: List[_H2HGame] = []
    for block in data.split("¬~")[:20]:
        if "KC÷" not in block:
            continue
        ts = 0
        g1 = g2 = 0
        for part in block.split("¬"):
            if part.startswith("KC÷"):
                try:
                    ts = int(part[3:])
                except ValueError:
                    ts = 0
            elif part.startswith("KL÷"):
                score = part[3:]
                bits = score.split(":")
                if len(bits) == 2:
                    try:
                        g1 = int(bits[0])
                        g2 = int(bits[1])
                    except ValueError:
                        g1 = g2 = 0
        if ts and (g1 or g2 or "KL÷" in block):
            games.append(
                _H2HGame(
                    date=datetime.fromtimestamp(ts),
                    home_score=g1,
                    away_score=g2,
                )
            )
    return games[:10]


def fetch_bts_h2h(match_id: str, settings: MatchSettings) -> Tuple[List[_H2HGame], List[_H2HGame]]:
    url = f"https://{settings.sourcer}x/feed/df_hh_1_{match_id}"
    text = fetch_feed(url)
    parts = text.split("~KA÷")
    home = _parse_h2h_block(parts[2]) if len(parts) > 2 else []
    away = _parse_h2h_block(parts[3]) if len(parts) > 3 else []
    return home, away


def analyze_h2h_condition(
    home_games: List[_H2HGame],
    away_games: List[_H2HGame],
) -> Dict[str, Any]:
    """В 5 последних очных — 2 победы хозяев и 2 победы гостей."""
    all_games = sorted(home_games + away_games, key=lambda g: g.date, reverse=True)[:5]
    home_wins = away_wins = draws = btts_yes = 0
    for game in all_games:
        if game.home_score > game.away_score:
            home_wins += 1
        elif game.away_score > game.home_score:
            away_wins += 1
        else:
            draws += 1
        if game.home_score >= 1 and game.away_score >= 1:
            btts_yes += 1
    total = len(all_games)
    btts_rate = btts_yes / total if total else 0.0
    return {
        "total_games_analyzed": total,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "btts_yes": btts_yes,
        "btts_rate": btts_rate,
        "condition_met": home_wins == 2 and away_wins == 2,
        "games": [
            {
                "date": g.date.strftime("%Y-%m-%d"),
                "score": f"{g.home_score}:{g.away_score}",
            }
            for g in all_games
        ],
    }


def max_btts_yes_odds(odds_data) -> float:
    best = 0.0
    for bk in getattr(odds_data, "bookmakers", []) or []:
        market = bk.markets.get("BTTS_YES")
        if market and market.current:
            try:
                val = float(market.current)
            except (TypeError, ValueError):
                continue
            if val > best:
                best = val
    return best


def compute_bts_prediction(
    match_id: str,
    home: str,
    away: str,
    settings: MatchSettings,
    *,
    odds_data=None,
) -> Optional[Dict[str, Any]]:
    """None — условие не выполнено или нет кф ОЗ."""
    if int(getattr(settings, "sport", 1) or 1) != 1:
        return None
    home_games, away_games = fetch_bts_h2h(match_id, settings)
    stats = analyze_h2h_condition(home_games, away_games)
    if not stats["condition_met"]:
        return None
    yes_odds = max_btts_yes_odds(odds_data) if odds_data else 0.0
    if yes_odds <= 0:
        return None
    btts_rate = float(stats["btts_rate"])
    diff = btts_rate - (1.0 / yes_odds)
    return {
        "prediction": BTS_PREDICTION,
        "odds": yes_odds,
        "btts_rate": btts_rate,
        "difference": diff,
        "notes": json.dumps(
            {"btts_rate": btts_rate, "difference": diff, "h2h": stats},
            ensure_ascii=False,
        ),
        "head_to_head_stats": stats,
    }
