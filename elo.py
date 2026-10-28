"""ELO rating system for teams across all sports."""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from db import get_db_connection, invalidate_cache

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

INITIAL_RATING: float = 1500.0
HOME_ADVANTAGE: float = 100.0
K_FACTOR_NEW: float = 32.0
K_FACTOR_ESTABLISHED: float = 24.0
MATCHES_THRESHOLD_NEW: int = 10

# ============================================================================
# ЧИСТЫЕ ФУНКЦИИ РАСЧЁТА ELO
# ============================================================================


def compute_expected_rating(rating_home: float, rating_away: float) -> tuple[float, float]:
    """Ожидание результата с учётом домашнего преимущества.

    E_home = 1 / (1 + 10^((R_away - (R_home + 100)) / 400))
    E_away = 1 - E_home
    """
    adjusted_home = rating_home + HOME_ADVANTAGE
    diff = rating_away - adjusted_home
    exponent = diff / 400.0
    expected_home = 1.0 / (1.0 + 10.0 ** exponent)
    expected_away = 1.0 - expected_home
    return (expected_home, expected_away)


def compute_elo_update(
    rating_old: float, expected: float, actual: float, matches_played: int
) -> float:
    """Новый рейтинг после матча.

    K = 32 если < 10 матчей, иначе 24.
    R_new = R_old + K * (actual - expected)
    """
    k = K_FACTOR_NEW if matches_played < MATCHES_THRESHOLD_NEW else K_FACTOR_ESTABLISHED
    return rating_old + k * (actual - expected)


def calculate_match_elo(
    home_rating: float,
    away_rating: float,
    score_home: int,
    score_away: int,
    *,
    home_matches: int = 0,
    away_matches: int = 0,
) -> dict[str, float]:
    """Вычислить изменения ELO для матча.

    home_matches/away_matches нужны для выбора K: у новой команды (<10 матчей)
    K=32, у устоявшейся — 24. Раньше сюда всегда передавался 0, поэтому K
    оставался максимальным независимо от опыта команды.

    Возвращает:
        home_expected, away_expected, home_actual, away_actual,
        home_rating_delta, away_rating_delta,
        home_new_rating, away_new_rating
    """
    expected_home, expected_away = compute_expected_rating(home_rating, away_rating)

    # Определяем фактический результат
    if score_home > score_away:
        home_actual: float = 1.0
        away_actual: float = 0.0
    elif score_home < score_away:
        home_actual = 0.0
        away_actual = 1.0
    else:
        home_actual = 0.5
        away_actual = 0.5

    # Вычисляем дельты с учётом числа сыгранных матчей (влияет на K).
    home_delta = (
        compute_elo_update(home_rating, expected_home, home_actual, home_matches)
        - home_rating
    )
    away_delta = (
        compute_elo_update(away_rating, expected_away, away_actual, away_matches)
        - away_rating
    )

    return {
        "home_expected": expected_home,
        "away_expected": expected_away,
        "home_actual": home_actual,
        "away_actual": away_actual,
        "home_rating_delta": home_delta,
        "away_rating_delta": away_delta,
        "home_new_rating": home_rating + home_delta,
        "away_new_rating": away_rating + away_delta,
    }


# ============================================================================
# РАБОТА С БД
# ============================================================================


def _ensure_initial_elo(conn: sqlite3.Connection, team_id: int, sport: int) -> None:
    """Инициализировать ELO для команды, если нет записи."""
    row = conn.execute(
        "SELECT rating, matches_played FROM team_elo_ratings WHERE team_id = ? AND sport = ?",
        (team_id, sport),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO team_elo_ratings (team_id, sport, rating, matches_played, wins, losses, draws)
            VALUES (?, ?, ?, 0, 0, 0, 0)
            """,
            (team_id, sport, INITIAL_RATING),
        )


def get_team_elo(team_id: int, sport: int) -> dict[str, Any] | None:
    """Получить текущий ELO для команды в виде спорта."""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT ter.*, t.name AS team_name
            FROM team_elo_ratings ter
            JOIN teams t ON t.id = ter.team_id
            WHERE ter.team_id = ? AND ter.sport = ?
            """,
            (team_id, sport),
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_all_elo(
    sport: int | None = None,
    limit: int = 500,
    offset: int = 0,
    sort: str = "rating",
    order: str = "desc",
) -> dict[str, Any]:
    """Получить все ELO-рейтинги с фильтрацией."""
    valid_sort = {"rating", "matches_played", "wins", "draws", "losses", "team_name"}
    if sort not in valid_sort:
        sort = "rating"
    order = "DESC" if order.lower() == "desc" else "ASC"

    sort_col_map = {
        "team_name": "t.name",
        "rating": "ter.rating",
        "matches_played": "ter.matches_played",
        "wins": "ter.wins",
        "draws": "ter.draws",
        "losses": "ter.losses",
    }
    order_by = f"{sort_col_map[sort]} {order}"

    where_clauses = ["1=1"]
    params: list[Any] = []

    if sport is not None:
        where_clauses.append("ter.sport = ?")
        params.append(sport)

    where_sql = " AND ".join(where_clauses)

    with get_db_connection() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM team_elo_ratings ter
            JOIN teams t ON t.id = ter.team_id
            WHERE {where_sql}
            """,
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT ter.team_id, t.name AS team_name, ter.sport,
                   ter.rating, ter.matches_played, ter.wins, ter.draws, ter.losses,
                   ter.last_updated
            FROM team_elo_ratings ter
            JOIN teams t ON t.id = ter.team_id
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

        items = [dict(r) for r in rows]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def update_elo_for_match(match_id: str) -> dict[str, Any] | None:
    """Обновить ELO для завершённого матча.

    Возвращает dict с新旧 рейтингами или None если матч не завершён/не найден.
    """
    from match_settle import is_finished_status

    with get_db_connection() as conn:
        # Получаем данные матча
        row = conn.execute(
            """
            SELECT m.match_id, m.sport, m.score_home, m.score_away,
                   m.match_status, m.home_team_id, m.away_team_id,
                   th.name AS home_name, ta.name AS away_name
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.match_id = ?
            """,
            (match_id,),
        ).fetchone()

        if not row:
            return None

        match = dict(row)

        # Проверяем что матч завершён
        if not is_finished_status(
            match["match_status"], match["score_home"], match["score_away"]
        ):
            return None

        # Проверяем что есть счёт
        if match["score_home"] is None or match["score_away"] is None:
            return None

        sport = match["sport"]
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]
        score_home = int(match["score_home"])
        score_away = int(match["score_away"])

        # Получаем текущие ELO
        _ensure_initial_elo(conn, home_id, sport)
        _ensure_initial_elo(conn, away_id, sport)

        home_elo = conn.execute(
            "SELECT * FROM team_elo_ratings WHERE team_id = ? AND sport = ?",
            (home_id, sport),
        ).fetchone()
        away_elo = conn.execute(
            "SELECT * FROM team_elo_ratings WHERE team_id = ? AND sport = ?",
            (away_id, sport),
        ).fetchone()

        home_rating = float(home_elo["rating"])
        away_rating = float(away_elo["rating"])
        home_matches = int(home_elo["matches_played"])
        away_matches = int(away_elo["matches_played"])

        # Вычисляем ELO — передаём число матчей, чтобы K зависел от опыта.
        result = calculate_match_elo(
            home_rating,
            away_rating,
            score_home,
            score_away,
            home_matches=home_matches,
            away_matches=away_matches,
        )

        # Новые значения
        home_new = round(home_rating + result["home_rating_delta"], 2)
        away_new = round(away_rating + result["away_rating_delta"], 2)

        # Определяем результат для статистики
        if score_home > score_away:
            home_result = "win"
            away_result = "loss"
        elif score_home < score_away:
            home_result = "loss"
            away_result = "win"
        else:
            home_result = "draw"
            away_result = "draw"

        # Обновляем ELO
        conn.execute(
            """
            UPDATE team_elo_ratings
            SET rating = ?, matches_played = matches_played + 1,
                wins = wins + ?, draws = draws + ?, losses = losses + ?,
                last_updated = datetime('now')
            WHERE team_id = ? AND sport = ?
            """,
            (
                home_new,
                1 if home_result == "win" else 0,
                1 if home_result == "draw" else 0,
                1 if home_result == "loss" else 0,
                home_id,
                sport,
            ),
        )
        conn.execute(
            """
            UPDATE team_elo_ratings
            SET rating = ?, matches_played = matches_played + 1,
                wins = wins + ?, draws = draws + ?, losses = losses + ?,
                last_updated = datetime('now')
            WHERE team_id = ? AND sport = ?
            """,
            (
                away_new,
                1 if away_result == "win" else 0,
                1 if away_result == "draw" else 0,
                1 if away_result == "loss" else 0,
                away_id,
                sport,
            ),
        )

        # Сохраняем историю
        conn.execute(
            """
            INSERT INTO elo_rating_history
            (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                home_id,
                sport,
                home_rating,
                home_new,
                result["home_rating_delta"],
                result["home_expected"],
                result["home_actual"],
            ),
        )
        conn.execute(
            """
            INSERT INTO elo_rating_history
            (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                away_id,
                sport,
                away_rating,
                away_new,
                result["away_rating_delta"],
                result["away_expected"],
                result["away_actual"],
            ),
        )

        conn.commit()
        invalidate_cache()

        return {
            "match_id": match_id,
            "sport": sport,
            "home_team": match["home_name"],
            "away_team": match["away_name"],
            "score_home": score_home,
            "score_away": score_away,
            "elo_before": {"home": home_rating, "away": away_rating},
            "elo_after": {"home": home_new, "away": away_new},
            "delta": {
                "home": round(result["home_rating_delta"], 2),
                "away": round(result["away_rating_delta"], 2),
            },
        }


def recalculate_all_elo(sport: int | None = None) -> dict[str, Any]:
    """Полный пересчёт ELO по всей истории матчей."""
    import time

    start_time = time.time()

    with get_db_connection() as conn:
        # Определяем фильтры
        where = ["m.match_status IS NOT NULL", "m.score_home IS NOT NULL", "m.score_away IS NOT NULL"]
        params: list[Any] = []

        if sport is not None:
            where.append("m.sport = ?")
            params.append(sport)

        where_sql = " AND ".join(where)

        # Получаем все завершённые матчи по дате
        matches = conn.execute(
            f"""
            SELECT m.match_id, m.sport, m.score_home, m.score_away,
                   m.home_team_id, m.away_team_id
            FROM matches m
            WHERE {where_sql}
              AND (m.match_status LIKE '%заверш%'
                   OR m.match_status LIKE '%законч%'
                   OR m.match_status LIKE '%после овертайм%'
                   OR m.match_status LIKE '%после буллит%'
                   OR m.match_status LIKE '%тех. пораж%'
                   OR m.match_status LIKE '%неявк%')
            ORDER BY m.match_date ASC, m.id ASC
            """,
            params,
        ).fetchall()

        # Сбрасываем все ELO
        conn.execute("DELETE FROM team_elo_ratings")
        conn.execute("DELETE FROM elo_rating_history")

        teams_processed: set[int] = set()
        matches_processed = 0

        for match in matches:
            m = dict(match)
            sport_m = m["sport"]
            home_id = m["home_team_id"]
            away_id = m["away_team_id"]
            score_home = int(m["score_home"])
            score_away = int(m["score_away"])

            # Инициализируем ELO
            _ensure_initial_elo(conn, home_id, sport_m)
            _ensure_initial_elo(conn, away_id, sport_m)
            teams_processed.add(home_id)
            teams_processed.add(away_id)

            # Получаем текущие ELO
            home_elo = conn.execute(
                "SELECT * FROM team_elo_ratings WHERE team_id = ? AND sport = ?",
                (home_id, sport_m),
            ).fetchone()
            away_elo = conn.execute(
                "SELECT * FROM team_elo_ratings WHERE team_id = ? AND sport = ?",
                (away_id, sport_m),
            ).fetchone()

            home_rating = float(home_elo["rating"])
            away_rating = float(away_elo["rating"])

            # Вычисляем
            result = calculate_match_elo(home_rating, away_rating, score_home, score_away)

            home_new = round(home_rating + result["home_rating_delta"], 2)
            away_new = round(away_rating + result["away_rating_delta"], 2)

            # Определяем результат
            if score_home > score_away:
                home_result, away_result = "win", "loss"
            elif score_home < score_away:
                home_result, away_result = "loss", "win"
            else:
                home_result, away_result = "draw", "draw"

            # Обновляем
            conn.execute(
                """
                UPDATE team_elo_ratings
                SET rating = ?, matches_played = matches_played + 1,
                    wins = wins + ?, draws = draws + ?, losses = losses + ?,
                    last_updated = datetime('now')
                WHERE team_id = ? AND sport = ?
                """,
                (
                    home_new,
                    1 if home_result == "win" else 0,
                    1 if home_result == "draw" else 0,
                    1 if home_result == "loss" else 0,
                    home_id,
                    sport_m,
                ),
            )
            conn.execute(
                """
                UPDATE team_elo_ratings
                SET rating = ?, matches_played = matches_played + 1,
                    wins = wins + ?, draws = draws + ?, losses = losses + ?,
                    last_updated = datetime('now')
                WHERE team_id = ? AND sport = ?
                """,
                (
                    away_new,
                    1 if away_result == "win" else 0,
                    1 if away_result == "draw" else 0,
                    1 if away_result == "loss" else 0,
                    away_id,
                    sport_m,
                ),
            )

            # Сохраняем историю
            conn.execute(
                """
                INSERT INTO elo_rating_history
                (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["match_id"], home_id, sport_m,
                    home_rating, home_new, result["home_rating_delta"],
                    result["home_expected"], result["home_actual"],
                ),
            )
            conn.execute(
                """
                INSERT INTO elo_rating_history
                (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["match_id"], away_id, sport_m,
                    away_rating, away_new, result["away_rating_delta"],
                    result["away_expected"], result["away_actual"],
                ),
            )

            matches_processed += 1

        conn.commit()
        invalidate_cache()

        duration = round((time.time() - start_time) * 1000, 1)

        return {
            "ok": True,
            "sport": sport,
            "teams_processed": len(teams_processed),
            "matches_processed": matches_processed,
            "duration_ms": duration,
        }


def get_elo_match_delta(match_id: str) -> dict[str, Any] | None:
    """Получить ELO-изменения для конкретного матча."""
    with get_db_connection() as conn:
        history = conn.execute(
            """
            SELECT erh.*, t.name AS team_name
            FROM elo_rating_history erh
            JOIN teams t ON t.id = erh.team_id
            WHERE erh.match_id = ?
            ORDER BY erh.team_id ASC
            """,
            (match_id,),
        ).fetchall()

        if not history:
            return None

        match_info = conn.execute(
            """
            SELECT m.match_id, m.sport, m.score_home, m.score_away,
                   th.name AS home_name, ta.name AS away_name
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.match_id = ?
            """,
            (match_id,),
        ).fetchone()

        if not match_info:
            return None

        mi = dict(match_info)
        records = [dict(r) for r in history]

        # Определяем кто home/away по имени команды
        home_record = None
        away_record = None
        for rec in records:
            if rec["team_name"] == mi["home_name"]:
                home_record = rec
            elif rec["team_name"] == mi["away_name"]:
                away_record = rec

        return {
            "match_id": mi["match_id"],
            "sport": mi["sport"],
            "home_team": mi["home_name"],
            "away_team": mi["away_name"],
            "score_home": mi["score_home"],
            "score_away": mi["score_away"],
            "elo_before": {
                "home": home_record["rating_before"] if home_record else 0,
                "away": away_record["rating_before"] if away_record else 0,
            },
            "elo_after": {
                "home": home_record["rating_after"] if home_record else 0,
                "away": away_record["rating_after"] if away_record else 0,
            },
            "delta": {
                "home": home_record["rating_delta"] if home_record else 0,
                "away": away_record["rating_delta"] if away_record else 0,
            },
        }
