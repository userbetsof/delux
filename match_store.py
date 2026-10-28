"""Очередь матчей в SQLite (замена листа «Список»)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from analysis_data import MatchInfo
from date_utils import normalize_match_date
from db import create_database, get_db_connection
from flashscore_feed import FIELD_SEP, ROW_SEP, FLASHSCORE_SOURCER, fetch_feed


def _fetch_match_score_from_dc(match_id: str, sport: int) -> Tuple[Optional[int], Optional[int]]:
    """Итоговый счёт матча из dc_ фида (поля DE/DF)."""
    url = f"https://{FLASHSCORE_SOURCER}x/feed/dc_{int(sport)}_{match_id}"
    try:
        text = fetch_feed(url, retries=2, timeout=30)
    except Exception:
        return None, None
    if not text:
        return None, None

    score_home = score_away = None
    for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
        key, sep, value = chunk.partition(FIELD_SEP)
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key == "DE":
            try:
                score_home = int(float(value))
            except (ValueError, TypeError):
                pass
        elif key == "DF":
            try:
                score_away = int(float(value))
            except (ValueError, TypeError):
                pass
    return score_home, score_away


@dataclass
class QueuedMatch:
    match_id: str
    sport: int
    tour_name: str = ""
    date_match: str = ""
    start_ts: Optional[int] = None
    home_name: str = ""
    away_name: str = ""
    country_id: str = ""
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    start_home: float = 0.0
    start_draw: float = 0.0
    start_away: float = 0.0
    current_home: float = 0.0
    current_draw: float = 0.0
    current_away: float = 0.0

    def to_match_info(self) -> MatchInfo:
        return MatchInfo(
            match_id=self.match_id,
            league=self.tour_name,
            date=self.date_match,
            home=self.home_name,
            away=self.away_name,
            country_id=self.country_id,
            score_home=self.score_home,
            score_away=self.score_away,
        )

    @classmethod
    def from_row(cls, row) -> "QueuedMatch":
        return cls(
            match_id=row["match_id"],
            sport=int(row["sport"] or 1),
            tour_name=row["tour_name"] or "",
            date_match=row["date_match"] or "",
            start_ts=row["start_ts"] if "start_ts" in row.keys() else None,
            home_name=row["home_name"] or "",
            away_name=row["away_name"] or "",
            country_id=row["country_id"] or "",
            score_home=row["score_home"],
            score_away=row["score_away"],
            start_home=float(row["start_home"] or 0),
            start_draw=float(row["start_draw"] or 0),
            start_away=float(row["start_away"] or 0),
            current_home=float(row["current_home"] or 0),
            current_draw=float(row["current_draw"] or 0),
            current_away=float(row["current_away"] or 0),
        )


def ensure_match_queue_schema() -> None:
    create_database()
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS match_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id VARCHAR(8) UNIQUE NOT NULL,
                sport INTEGER NOT NULL DEFAULT 1,
                tour_name TEXT,
                date_match TEXT,
                start_ts INTEGER,
                home_name TEXT,
                away_name TEXT,
                country_id TEXT,
                score_home INTEGER,
                score_away INTEGER,
                start_home REAL,
                start_draw REAL,
                start_away REAL,
                current_home REAL,
                current_draw REAL,
                current_away REAL,
                loaded_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(match_queue)").fetchall()}
        if "start_ts" not in cols:
            conn.execute("ALTER TABLE match_queue ADD COLUMN start_ts INTEGER")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_queue_sport ON match_queue(sport)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_queue_tour ON match_queue(tour_name)"
        )


def _normalize_league_name(name: str) -> str:
    return (name or "").strip().casefold()


def _league_allowed(tour_name: str, leagues: Optional[List[str]]) -> bool:
    """Точное совпадение названия лиги (без подстрок)."""
    if not leagues:
        return True
    name = _normalize_league_name(tour_name)
    if not name:
        return False
    for league in leagues:
        if name == _normalize_league_name(league):
            return True
    return False


def filter_matches_for_queue(
    matches: List[Dict],
    sport: int,
    *,
    leagues: Optional[List[str]] = None,
    min_games: int = 5,
    settings=None,
) -> Tuple[List[Dict], int, int]:
    """Отбор матчей: избранная лига (точно) + минимум сыгранных игр в таблице."""
    from analysis_data import build_settings, season_games_ready

    if settings is None:
        settings = build_settings(sport=int(sport or 1))
    table_cache: Dict[str, list] = {}
    kept: List[Dict] = []
    skipped_league = 0
    skipped_tour = 0
    for match in matches:
        tour = match.get("tour_name") or ""
        if not _league_allowed(tour, leagues):
            skipped_league += 1
            continue
        if min_games > 0:
            ready, _ = season_games_ready(
                settings,
                str(match.get("match_id") or ""),
                str(match.get("home_name") or ""),
                str(match.get("away_name") or ""),
                min_games=min_games,
                table_cache=table_cache,
            )
            if not ready:
                skipped_tour += 1
                continue
        kept.append(match)
    return kept, skipped_league, skipped_tour


def clear_queue(sport: Optional[int] = None) -> None:
    ensure_match_queue_schema()
    with get_db_connection() as conn:
        if sport is None:
            conn.execute("DELETE FROM match_queue")
        else:
            conn.execute("DELETE FROM match_queue WHERE sport = ?", (sport,))


def upsert_matches(
    matches: List[Dict],
    sport: int,
    *,
    leagues: Optional[List[str]] = None,
    replace_sport: bool = False,
) -> int:
    """Сохранить матчи в очередь. Возвращает число записанных строк."""
    ensure_match_queue_schema()
    if replace_sport:
        clear_queue(sport)

    written = 0
    with get_db_connection() as conn:
        for match in matches:
            tour = match.get("tour_name") or ""
            if not _league_allowed(tour, leagues):
                continue
            conn.execute(
                """
                INSERT INTO match_queue (
                    match_id, sport, tour_name, date_match, start_ts, home_name, away_name,
                    country_id, score_home, score_away,
                    start_home, start_draw, start_away,
                    current_home, current_draw, current_away, loaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(match_id) DO UPDATE SET
                    sport=excluded.sport,
                    tour_name=excluded.tour_name,
                    date_match=excluded.date_match,
                    start_ts=excluded.start_ts,
                    home_name=excluded.home_name,
                    away_name=excluded.away_name,
                    country_id=excluded.country_id,
                    score_home=excluded.score_home,
                    score_away=excluded.score_away,
                    start_home=excluded.start_home,
                    start_draw=excluded.start_draw,
                    start_away=excluded.start_away,
                    current_home=excluded.current_home,
                    current_draw=excluded.current_draw,
                    current_away=excluded.current_away,
                    loaded_at=datetime('now')
                """,
                (
                    match["match_id"],
                    sport,
                    tour,
                    normalize_match_date(match.get("date_match") or ""),
                    match.get("start_ts"),
                    match.get("home_name") or "",
                    match.get("away_name") or "",
                    match.get("country_id") or "",
                    match.get("score_home"),
                    match.get("score_away"),
                    match.get("start_home"),
                    match.get("start_draw"),
                    match.get("start_away"),
                    match.get("current_home"),
                    match.get("current_draw"),
                    match.get("current_away"),
                ),
            )
            written += 1
    return written


def get_queued_match(match_id: str) -> Optional[QueuedMatch]:
    ensure_match_queue_schema()
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM match_queue WHERE match_id = ?",
            (match_id,),
        )
        row = cur.fetchone()
    return QueuedMatch.from_row(row) if row else None


def list_analyzed_matches(*, sport: Optional[int] = None) -> List[QueuedMatch]:
    """Матчи, по которым уже есть calc-прогнозы (для догона BTS / StavkaTV / Moneyway)."""
    sql = """
        SELECT
            m.match_id,
            m.sport,
            COALESCE(c.name || ': ' || l.name, l.name, '') AS tour_name,
            m.match_date AS date_match,
            t1.name AS home_name,
            t2.name AS away_name
        FROM matches m
        LEFT JOIN leagues l ON l.id = m.league_id
        LEFT JOIN countries c ON c.id = l.country_id
        JOIN teams t1 ON t1.id = m.home_team_id
        JOIN teams t2 ON t2.id = m.away_team_id
        WHERE EXISTS (
            SELECT 1 FROM strategy_predictions sp
            WHERE sp.match_id = m.match_id AND sp.strategy_id IN (1, 2, 3)
        )
    """
    params: list = []
    if sport is not None:
        sql += " AND m.sport = ?"
        params.append(sport)
    sql += " ORDER BY m.match_date, m.match_id"
    with get_db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        QueuedMatch(
            match_id=row["match_id"],
            sport=int(row["sport"] or 1),
            tour_name=row["tour_name"] or "",
            date_match=row["date_match"] or "",
            home_name=row["home_name"] or "",
            away_name=row["away_name"] or "",
        )
        for row in rows
    ]


def list_matches_for_strategy(
    *,
    sport: Optional[int] = None,
    leagues_by_sport: Optional[Dict[int, Optional[List[str]]]] = None,
) -> List[QueuedMatch]:
    """Очередь + уже разобранные матчи, без дублей."""
    seen: Dict[str, QueuedMatch] = {}
    for q in list_queued_matches(
        leagues_by_sport=leagues_by_sport,
        sport=sport,
        new_only=False,
    ):
        seen[q.match_id] = q
    for q in list_analyzed_matches(sport=sport):
        if q.match_id in seen:
            continue
        if leagues_by_sport is not None:
            if q.sport not in leagues_by_sport:
                continue
            allowed = leagues_by_sport[q.sport]
            if allowed is not None and not _league_allowed(q.tour_name, allowed):
                continue
        seen[q.match_id] = q
    return list(seen.values())


def match_needs_analysis(match_id: str) -> bool:
    """True если матча нет в matches или анализ неполный (нет 3 прогнозов / 10 стратегий)."""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(DISTINCT strategy_id) FROM strategy_predictions WHERE match_id = ?) AS preds,
                (SELECT COUNT(*) FROM outcome_probabilities WHERE match_id = ?) AS outcomes
            FROM matches
            WHERE match_id = ?
            """,
            (match_id, match_id, match_id),
        ).fetchone()
        if not row:
            return True
        preds = int(row[0] or 0)
        outcomes = int(row[1] or 0)
        return preds < 3 or outcomes < 10


def list_queued_matches(
    *,
    leagues: Optional[List[str]] = None,
    leagues_by_sport: Optional[Dict[int, Optional[List[str]]]] = None,
    sport: Optional[int] = None,
    new_only: bool = False,
    limit: int = 0,
) -> List[QueuedMatch]:
    ensure_match_queue_schema()
    sql = "SELECT * FROM match_queue WHERE 1=1"
    params: list = []
    if sport is not None:
        sql += " AND sport = ?"
        params.append(sport)
    sql += " ORDER BY date_match, match_id"

    with get_db_connection() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()

    result: List[QueuedMatch] = []
    for row in rows:
        qm = QueuedMatch.from_row(row)
        if leagues_by_sport is not None:
            if qm.sport not in leagues_by_sport:
                continue
            allowed = leagues_by_sport[qm.sport]
            if allowed is not None and not _league_allowed(qm.tour_name, allowed):
                continue
        elif leagues and not _league_allowed(qm.tour_name, leagues):
            continue
        if new_only and not match_needs_analysis(qm.match_id):
            continue
        result.append(qm)
        if limit > 0 and len(result) >= limit:
            break
    return result
