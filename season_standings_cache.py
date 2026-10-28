"""Кэш таблиц на момент матча (по турниру/сезону).

Зачем: анализ сезона из 380 матчей заново скачивает tr_-фид, чтобы
восстановить таблицу на момент каждого матча. При прерывании вся работа
теряется, а таблица для каждого матча критична — от неё зависит статистика.

Что хранится: восстановленные standings (overall/home/away) по match_id
для конкретного (sport, country, tournament_key, season_id). Каждая запись
пишется сразу после расчёта, поэтому прерванный прогон продолжается
с уже готовыми таблицами.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional


def add_season_standings_table(cursor: sqlite3.Cursor) -> None:
    """Таблица кэша таблиц: одна запись на матч сезона."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS season_standings_cache (
            sport INTEGER NOT NULL,
            country INTEGER NOT NULL,
            tournament_key TEXT NOT NULL,
            season_id TEXT NOT NULL,
            match_id TEXT NOT NULL,
            kickoff_ts INTEGER NOT NULL DEFAULT 0,
            standings_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (sport, country, tournament_key, season_id, match_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ssc_lookup "
        "ON season_standings_cache(sport, country, tournament_key, season_id)"
    )


def _conn() -> sqlite3.Connection:
    from db import get_db_connection

    return get_db_connection()


def get_cached_standings(
    match_id: str,
    *,
    sport: int,
    country: int,
    tournament_key: str,
    season_id: str,
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Восстановленная таблица из кэша или None."""
    if not (match_id and tournament_key and season_id):
        return None
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT standings_json FROM season_standings_cache
            WHERE sport = ? AND country = ? AND tournament_key = ?
              AND season_id = ? AND match_id = ?
            """,
            (int(sport), int(country), tournament_key, str(season_id), match_id),
        ).fetchone()
    if not row or not row[0]:
        return None
    try:
        data = json.loads(row[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_cached_standings(
    match_id: str,
    standings: Dict[str, List[Dict[str, Any]]],
    *,
    sport: int,
    country: int,
    tournament_key: str,
    season_id: str,
    kickoff_ts: int = 0,
) -> bool:
    """Сохранить восстановленную таблицу для матча (перезапись)."""
    if not (match_id and tournament_key and season_id and standings):
        return False
    payload = json.dumps(standings, ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO season_standings_cache
            (sport, country, tournament_key, season_id, match_id,
             kickoff_ts, standings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sport, country, tournament_key, season_id, match_id)
            DO UPDATE SET
                kickoff_ts = excluded.kickoff_ts,
                standings_json = excluded.standings_json
            """,
            (
                int(sport),
                int(country),
                tournament_key,
                str(season_id),
                match_id,
                int(kickoff_ts or 0),
                payload,
            ),
        )
        conn.commit()
    return True


def cache_stats(
    *, sport: int, country: int, tournament_key: str, season_id: str
) -> Dict[str, int]:
    """Сколько матчей сезона уже имеют закэшированную таблицу."""
    with _conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM season_standings_cache "
            "WHERE sport = ? AND country = ? AND tournament_key = ? AND season_id = ?",
            (int(sport), int(country), tournament_key, str(season_id)),
        ).fetchone()[0]
    return {"cached": int(total)}


def cache_season_standings(
    all_matches: List[Dict[str, Any]],
    *,
    sport: int,
    country: int,
    tournament_key: str,
    season_id: str,
    skip_existing: bool = True,
) -> Dict[str, int]:
    """Разом посчитать и закэшировать таблицу для всех матчей сезона.

    Один линейный проход (reconstruct_all_standings) вместо пересчёта
    с нуля для каждого матча. Возвращает {'computed': n, 'skipped': m}.
    """
    from archive_old_match import reconstruct_all_standings

    if not (all_matches and tournament_key and season_id):
        return {"computed": 0, "skipped": 0}

    per_match = reconstruct_all_standings(all_matches)
    computed = 0
    skipped = 0
    with _conn() as conn:
        existing: set[str] = set()
        if skip_existing:
            existing = {
                r[0]
                for r in conn.execute(
                    "SELECT match_id FROM season_standings_cache "
                    "WHERE sport = ? AND country = ? AND tournament_key = ? "
                    "AND season_id = ?",
                    (int(sport), int(country), tournament_key, str(season_id)),
                ).fetchall()
            }
        rows = []
        for mid, standings in per_match.items():
            if mid in existing:
                skipped += 1
                continue
            kickoff = next(
                (
                    int(m.get("kickoff_ts") or 0)
                    for m in all_matches
                    if m.get("match_id") == mid
                ),
                0,
            )
            rows.append(
                (
                    int(sport),
                    int(country),
                    tournament_key,
                    str(season_id),
                    mid,
                    kickoff,
                    json.dumps(standings, ensure_ascii=False),
                )
            )
        if rows:
            conn.executemany(
                """
                INSERT INTO season_standings_cache
                (sport, country, tournament_key, season_id, match_id,
                 kickoff_ts, standings_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sport, country, tournament_key, season_id, match_id)
                DO UPDATE SET
                    kickoff_ts = excluded.kickoff_ts,
                    standings_json = excluded.standings_json
                """,
                rows,
            )
            conn.commit()
            computed = len(rows)
    return {"computed": computed, "skipped": skipped}
