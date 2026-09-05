"""Загрузка завершённых матчей и коэффициентов из matches.db."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from db import get_database_path
from settings import DeluxSettings


@dataclass
class FinishedMatch:
    match_id: str
    sport: int
    tour_name: str
    home_name: str
    away_name: str
    score_home: int
    score_away: int
    odds: Dict[str, float]


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        try:
            v = float(str(value).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None
    return v if v > 1 else None


def load_odds_index(conn: sqlite3.Connection) -> Dict[str, Dict[str, float]]:
    idx: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in conn.execute(
        """
        SELECT match_id, market_name, odds_value
        FROM odds
        WHERE odds_value IS NOT NULL AND market_name IS NOT NULL
        """
    ):
        odds = _to_float(row["odds_value"])
        if not odds:
            continue
        key = str(row["market_name"]).upper().strip()
        prev = idx[row["match_id"]].get(key)
        if prev is None or odds > prev:
            idx[row["match_id"]][key] = odds
    return idx


def load_finished_matches(
    db_path: Optional[str] = None,
    *,
    favorite_leagues_only: bool = True,
) -> List[FinishedMatch]:
    cfg = DeluxSettings.from_env()
    path = db_path or get_database_path()

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        odds_idx = load_odds_index(conn)
        rows = conn.execute(
            """
            SELECT
                m.match_id,
                m.sport,
                m.score_home,
                m.score_away,
                COALESCE(q.tour_name, l.name, '') AS tour_name,
                COALESCE(q.home_name, th.name, '') AS home_name,
                COALESCE(q.away_name, ta.name, '') AS away_name
            FROM matches m
            LEFT JOIN match_queue q ON q.match_id = m.match_id
            LEFT JOIN leagues l ON l.id = m.league_id
            LEFT JOIN teams th ON th.id = m.home_team_id
            LEFT JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.score_home IS NOT NULL
              AND m.score_away IS NOT NULL
              AND (m.match_status = 'Завершен' OR m.match_status LIKE '%верш%')
            """
        ).fetchall()
    finally:
        conn.close()

    result: List[FinishedMatch] = []
    for row in rows:
        sport = int(row["sport"] or 1)
        tour = row["tour_name"] or ""
        if favorite_leagues_only and not cfg.is_favorite_league(sport, tour):
            continue
        match_odds = odds_idx.get(row["match_id"], {})
        if not match_odds:
            continue
        result.append(
            FinishedMatch(
                match_id=row["match_id"],
                sport=sport,
                tour_name=tour,
                home_name=row["home_name"] or "",
                away_name=row["away_name"] or "",
                score_home=int(row["score_home"]),
                score_away=int(row["score_away"]),
                odds=match_odds,
            )
        )
    return result
