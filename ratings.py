"""Рейтинговые системы: Glicko-2 и OpenSkill.

Glicko-2 — улучшение ELO с учётом неопределённости (RD) и волатильности.
OpenSkill — система для любых форматов (1-1, 1-X-1, team vs team).
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from db import get_db_connection, invalidate_cache


# ============================================================================
# КОНСТАНТЫ
# ============================================================================

# Glicko-2 параметры
GLICKO2_INITIAL_RATING: float = 1500.0
GLICKO2_INITIAL_RD: float = 350.0  # Rating Deviation
GLICKO2_VOLATILITY: float = 0.06   # Volatility (σ) — стартовое значение из статьи
GLICKO2_TIME_MARKUP: float = 1.0   # Time markup (τ)
GLICKO2_CONSTANT: float = 173.28   # q * sqrt(sum of squares)
# Масштаб шкалы Glicko-2: (rating - 1500) / 173.7178 — «внутренние» единицы.
GLICKO2_SCALE: float = 173.7178
# τ (tau) — насколько свободно volatility меняется между периодами.
# 0.5 — стандарт Glickman; больше → быстрее «разгон» и нестабильность.
GLICKO2_TAU: float = 0.5
# Параметры итерационного поиска volatility (метод Illinois).
MAX_ITER: int = 100
K_ITER_STEP: float = 1.0
# Преимущество домашнего поля в пунктах рейтинга (как в elo.HOME_ADVANTAGE).
HOME_ADVANTAGE_POINTS: float = 100.0

# OpenSkill параметры (по умолчанию)
OPENSKILL_MU_INIT: float = 25.0    # μ = rating/2 - 10
OPENSKILL_SIGMA_INIT: float = 25.0 / 3  # σ = μ/3


# ============================================================================
# Glicko-2 — ЧИСТЫЕ ФУНКЦИИ
# ============================================================================

@dataclass
class Glicko2Player:
    """Игрок/команда в системе Glicko-2."""
    rating: float = GLICKO2_INITIAL_RATING
    rd: float = GLICKO2_INITIAL_RD
    volatility: float = GLICKO2_VOLATILITY


@dataclass
class Glicko2Match:
    """Результат матча для Glicko-2."""
    opponent_rating: float
    opponent_rd: float
    result: float  # 1=победа, 0.5=ничья, 0=поражение
    home_advantage: float = 0.0  # +100 для хозяев


def _sigmoid(x: float) -> float:
    """Численно устойчивый логистический сигмоид (math.exp падает при |x|>709)."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def glicko2_expected_score(rating: float, rd: float,
                           opponent_rating: float, opponent_rd: float,
                           home_advantage: float = 0.0) -> float:
    """Ожидаемый счёт (0-1) для Glicko-2.

    E = 1 / (1 + exp(-g(φ) * (μ - μ_opp))), где
      φ = sqrt((RD² + RD_opp²)) / SCALE   — суммарная неопределённость,
      g(φ) = 1 / sqrt(1 + 3φ²/π²),
      μ   = (rating + HA - opponent_rating) / SCALE.

    Важно: g берётся от ОБОИХ RD — чем менее известен соперник, тем меньше
    вес имеет разница рейтингов (исход менее предсказуем).
    """
    phi = math.sqrt(rd ** 2 + opponent_rd ** 2) / GLICKO2_SCALE
    g_phi = 1.0 / math.sqrt(1.0 + 3.0 * phi ** 2 / math.pi ** 2)
    mu_diff = (rating + home_advantage - opponent_rating) / GLICKO2_SCALE
    return _sigmoid(g_phi * mu_diff)


def _update_volatility(
    player: Glicko2Player,
    matches: List[Glicko2Match],
    *,
    tau: float = GLICKO2_TAU,
    eps: float = 1e-6,
) -> float:
    """Оценка volatility методом Illinois (Glickman, Glicko-2, шаг 5).

    Volatility показывает, насколько «рваные» результаты у команды: она растёт,
    когда исходы регулярно расходятся с ожиданием, и падает, когда команда
    играет предсказуемо. Именно она определяет, как быстро рейтинг «разгоняется».

    Если результатов ещё нет — возвращаем текущее значение.
    """
    if not matches:
        return player.volatility

    # a = ln(σ²); параметры в «внутренней» шкале Glicko-2 (1500 — среднее,
    # 173.7178 — масштаб), поэтому переводим rating/RD туда.
    a = math.log(player.volatility ** 2)

    mu = (player.rating - GLICKO2_INITIAL_RATING) / GLICKO2_SCALE
    phi = player.rd / GLICKO2_SCALE

    # v — дисперсия информации от матчей, delta — нормированное отклонение.
    # В статье: v = 1/Σ g²E(1−E), delta = v·Σ g(s−E).
    v_inv = 0.0
    delta_sum = 0.0
    for match in matches:
        opp_mu = (match.opponent_rating - GLICKO2_INITIAL_RATING) / GLICKO2_SCALE
        opp_phi = match.opponent_rd / GLICKO2_SCALE
        ha = (match.home_advantage or 0.0) / GLICKO2_SCALE
        g = 1.0 / math.sqrt(1.0 + 3.0 * opp_phi ** 2 / math.pi ** 2)
        e = _sigmoid(g * (mu + ha - opp_mu))
        v_inv += g ** 2 * e * (1.0 - e)
        delta_sum += g * (float(match.result) - e)

    if v_inv <= 0:
        return player.volatility

    v_inv = max(v_inv, 1e-12)
    v = 1.0 / v_inv
    delta = max(-1e6, min(1e6, delta_sum * v))
    delta_sq = min(delta ** 2, 1e12)
    phi_sq = phi ** 2

    def f(x: float) -> float:
        ex = math.exp(min(x, 700.0))
        num = ex * (delta_sq - phi_sq - v - ex)
        den = 2.0 * (phi_sq + v + ex) ** 2
        return num / den - (x - a) / (tau ** 2)

    # Начальные границы поиска (шаг 5.1).
    A = a
    if delta_sq > phi_sq + v:
        B = math.log(delta_sq - phi_sq - v)
    else:
        B = a - K_ITER_STEP * tau
        while f(B) < 0:
            B -= K_ITER_STEP * tau

    # Итерации Illinois (5.2–5.4).
    # eps фиксированной статьи (1e-6) на большом B слишком груб: exp(B/2)
    # раздувает ошибку до сотен раз. Используем относительную точность и
    # ограничиваем итоговую volatility разумным потолком.
    fA, fB = f(A), f(B)
    for _ in range(MAX_ITER):
        if abs(B - A) <= eps * max(1.0, abs(A), abs(B)):
            break
        if fB == fA:
            C = (A + B) / 2.0
        else:
            C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA = fA / 2.0
        B, fB = C, fC

    volatility = math.exp(B / 2.0)
    # Страховка: сходимость вне разумного диапазона — признак численного сбоя.
    # Диапазон вокруг стандартного σ₀ = 0.06 (Glickman).
    if not math.isfinite(volatility) or not (0.005 <= volatility <= 2.0):
        return player.volatility
    return volatility


def glicko2_update(player: Glicko2Player, matches: List[Glicko2Match]) -> Tuple[float, float, float]:
    """Обновление рейтинга, RD и volatility после серии матчей.

    Полная реализация Glicko-2 (Glickman 2022): volatile-оценка σ считается
    методом Illinois, а не остаётся константой — команда с рваными результатами
    получает более широкий шаг, предсказуемая — более узкий.

    Возвращает: (new_rating, new_rd, new_volatility)
    """
    if not matches:
        return player.rating, player.rd, player.volatility

    # Шаг 1: обновляем volatility
    new_volatility = _update_volatility(player, matches)

    # Шаг 2: переводим во внутреннюю шкалу
    mu = (player.rating - GLICKO2_INITIAL_RATING) / GLICKO2_SCALE
    phi = player.rd / GLICKO2_SCALE

    v_inv = 0.0
    delta_sum = 0.0
    for match in matches:
        opp_mu = (match.opponent_rating - GLICKO2_INITIAL_RATING) / GLICKO2_SCALE
        opp_phi = match.opponent_rd / GLICKO2_SCALE
        ha = (match.home_advantage or 0.0) / GLICKO2_SCALE
        g = 1.0 / math.sqrt(1.0 + 3.0 * opp_phi ** 2 / math.pi ** 2)
        e = _sigmoid(g * (mu + ha - opp_mu))
        v_inv += g ** 2 * e * (1.0 - e)
        delta_sum += g * (float(match.result) - e)

    if v_inv <= 0:
        return player.rating, player.rd, new_volatility

    # Шаг 3: новое RD
    phi_star = math.sqrt(phi ** 2 + new_volatility ** 2)
    new_phi = 1.0 / math.sqrt(1.0 / phi_star ** 2 + v_inv)

    # Шаг 4: новый рейтинг
    new_mu = mu + (new_phi ** 2) * delta_sum

    return (
        new_mu * GLICKO2_SCALE + GLICKO2_INITIAL_RATING,
        new_phi * GLICKO2_SCALE,
        new_volatility,
    )


# ============================================================================
# GlickO-2 — РАБОТА С БД
# ============================================================================

@dataclass
class Glicko2Team:
    """Команда в системе Glicko-2."""
    team_id: int
    sport: int
    rating: float = GLICKO2_INITIAL_RATING
    rd: float = GLICKO2_INITIAL_RD
    volatility: float = GLICKO2_VOLATILITY
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0


def _ensure_glicko2_initial(conn: sqlite3.Connection, team_id: int, sport: int) -> None:
    """Инициализировать Glicko-2 для команды, если нет записи."""
    row = conn.execute(
        "SELECT rating, rd, volatility FROM glicko2_ratings WHERE team_id = ? AND sport = ?",
        (team_id, sport),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO glicko2_ratings 
            (team_id, sport, rating, rd, volatility, matches_played, wins, draws, losses)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0)
            """,
            (team_id, sport, GLICKO2_INITIAL_RATING, GLICKO2_INITIAL_RD, GLICKO2_VOLATILITY),
        )


def update_glicko2_for_match(match_id: str) -> Optional[Dict[str, Any]]:
    """Обновить Glicko-2 для завершённого матча.
    
    Возвращает dict с新旧 рейтингами или None.
    """
    from match_settle import is_finished_status
    
    with get_db_connection() as conn:
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
        
        if not is_finished_status(
            match["match_status"], match["score_home"], match["score_away"]
        ):
            return None
        
        if match["score_home"] is None or match["score_away"] is None:
            return None
        
        sport = match["sport"]
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]
        score_home = int(match["score_home"])
        score_away = int(match["score_away"])
        
        # Получаем текущие Glicko-2
        _ensure_glicko2_initial(conn, home_id, sport)
        _ensure_glicko2_initial(conn, away_id, sport)
        
        home_glicko = conn.execute(
            "SELECT * FROM glicko2_ratings WHERE team_id = ? AND sport = ?",
            (home_id, sport),
        ).fetchone()
        away_glicko = conn.execute(
            "SELECT * FROM glicko2_ratings WHERE team_id = ? AND sport = ?",
            (away_id, sport),
        ).fetchone()
        
        home_rating = float(home_glicko["rating"])
        home_rd = float(home_glicko["rd"])
        home_vol = float(home_glicko["volatility"])
        
        away_rating = float(away_glicko["rating"])
        away_rd = float(away_glicko["rd"])
        away_vol = float(away_glicko["volatility"])
        
        # Вычисляем ожидаемый счёт
        home_expected = glicko2_expected_score(home_rating, home_rd, away_rating, away_rd, home_advantage=100.0)
        away_expected = 1.0 - home_expected
        
        # Фактический результат
        if score_home > score_away:
            home_actual = 1.0
            away_actual = 0.0
        elif score_home < score_away:
            home_actual = 0.0
            away_actual = 1.0
        else:
            home_actual = 0.5
            away_actual = 0.5

        # Полноценный Glicko-2: rating, RD и volatility обновляются по статье
        # Glickman, а не ELO-подобным коэффициентом. RD отдаётся апдейтом
        # (он уменьшается с числом матчей), а не домножается на 0.95.
        home_new, home_new_rd, home_vol_new = glicko2_update(
            Glicko2Player(home_rating, home_rd, home_vol),
            [
                Glicko2Match(
                    opponent_rating=away_rating,
                    opponent_rd=away_rd,
                    result=home_actual,
                    home_advantage=HOME_ADVANTAGE_POINTS,
                )
            ],
        )
        away_new, away_new_rd, away_vol_new = glicko2_update(
            Glicko2Player(away_rating, away_rd, away_vol),
            [
                Glicko2Match(
                    opponent_rating=home_rating,
                    opponent_rd=home_rd,
                    result=away_actual,
                    home_advantage=-HOME_ADVANTAGE_POINTS,
                )
            ],
        )
        home_new = round(home_new, 2)
        away_new = round(away_new, 2)
        home_new_rd = round(home_new_rd, 2)
        away_new_rd = round(away_new_rd, 2)
        home_vol = home_vol_new
        away_vol = away_vol_new
        
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
        
        # Обновляем Glicko-2
        conn.execute(
            """
            UPDATE glicko2_ratings
            SET rating = ?, rd = ?, volatility = ?,
                matches_played = matches_played + 1,
                wins = wins + ?, draws = draws + ?, losses = losses + ?,
                last_updated = datetime('now')
            WHERE team_id = ? AND sport = ?
            """,
            (
                home_new,
                home_new_rd,
                home_vol,
                1 if home_result == "win" else 0,
                1 if home_result == "draw" else 0,
                1 if home_result == "loss" else 0,
                home_id,
                sport,
            ),
        )
        conn.execute(
            """
            UPDATE glicko2_ratings
            SET rating = ?, rd = ?, volatility = ?,
                matches_played = matches_played + 1,
                wins = wins + ?, draws = draws + ?, losses = losses + ?,
                last_updated = datetime('now')
            WHERE team_id = ? AND sport = ?
            """,
            (
                away_new,
                away_new_rd,
                away_vol,
                1 if away_result == "win" else 0,
                1 if away_result == "draw" else 0,
                1 if away_result == "loss" else 0,
                away_id,
                sport,
            ),
        )
        
        # Пересчитываем ожидание по итоговым рейтингам (для истории).
        home_expected = glicko2_expected_score(
            home_rating, home_rd, away_rating, away_rd,
            home_advantage=HOME_ADVANTAGE_POINTS,
        )
        home_delta = round(home_new - home_rating, 2)
        away_delta = round(away_new - away_rating, 2)

        # Сохраняем историю
        conn.execute(
            """
            INSERT INTO glicko2_rating_history
            (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, home_id, sport,
                home_rating, home_new, home_delta,
                home_expected, home_actual,
            ),
        )
        conn.execute(
            """
            INSERT INTO glicko2_rating_history
            (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, away_id, sport,
                away_rating, away_new, away_delta,
                away_expected, away_actual,
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
            "glicko2_before": {"home": home_rating, "away": away_rating},
            "glicko2_after": {"home": home_new, "away": away_new},
            "rd_before": {"home": home_rd, "away": away_rd},
            "expected": {"home": round(home_expected, 3), "away": round(away_expected, 3)},
            "delta": {"home": round(home_delta, 2), "away": round(away_delta, 2)},
        }


def get_team_glicko2(team_id: int, sport: int) -> Optional[Dict[str, Any]]:
    """Получить текущий Glicko-2 для команды."""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT gr.*, t.name AS team_name
            FROM glicko2_ratings gr
            JOIN teams t ON t.id = gr.team_id
            WHERE gr.team_id = ? AND gr.sport = ?
            """,
            (team_id, sport),
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_all_glicko2(sport: Optional[int] = None, limit: int = 500, offset: int = 0) -> Dict[str, Any]:
    """Получить все Glicko-2 рейтинги."""
    where_clauses = ["1=1"]
    params: list[Any] = []
    
    if sport is not None:
        where_clauses.append("gr.sport = ?")
        params.append(sport)
    
    where_sql = " AND ".join(where_clauses)
    
    with get_db_connection() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM glicko2_ratings gr
            JOIN teams t ON t.id = gr.team_id
            WHERE {where_sql}
            """,
            params,
        ).fetchone()[0]
        
        rows = conn.execute(
            f"""
            SELECT gr.team_id, t.name AS team_name, gr.sport,
                   gr.rating, gr.rd, gr.volatility,
                   gr.matches_played, gr.wins, gr.draws, gr.losses,
                   gr.last_updated
            FROM glicko2_ratings gr
            JOIN teams t ON t.id = gr.team_id
            WHERE {where_sql}
            ORDER BY gr.rating DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        
        items = [dict(r) for r in rows]
    
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def recalculate_all_glicko2(sport: Optional[int] = None) -> Dict[str, Any]:
    """Полный пересчёт Glicko-2 по всей истории матчей."""
    import time
    start_time = time.time()
    
    with get_db_connection() as conn:
        where = ["m.match_status IS NOT NULL", "m.score_home IS NOT NULL", "m.score_away IS NOT NULL"]
        params: list[Any] = []
        
        if sport is not None:
            where.append("m.sport = ?")
            params.append(sport)
        
        where_sql = " AND ".join(where)
        
        matches = conn.execute(
            f"""
            SELECT m.match_id, m.sport, m.score_home, m.score_away,
                   m.home_team_id, m.away_team_id
            FROM matches m
            WHERE {where_sql}
              AND (
                  m.match_status = 'Завершен'
                  OR m.match_status LIKE '%овертайм%'
                  OR m.match_status LIKE '%буллит%'
                  OR m.match_status LIKE '%тех. пораж%'
                  OR m.match_status LIKE '%неявк%'
              )
            ORDER BY m.match_date ASC, m.id ASC
            """,
            params,
        ).fetchall()
        
        # Сбрасываем все Glicko-2
        conn.execute("DELETE FROM glicko2_ratings")
        conn.execute("DELETE FROM glicko2_rating_history")
        
        teams_processed = set()
        matches_processed = 0
        
        for match in matches:
            m = dict(match)
            sport_m = m["sport"]
            home_id = m["home_team_id"]
            away_id = m["away_team_id"]
            score_home = int(m["score_home"])
            score_away = int(m["score_away"])
            
            _ensure_glicko2_initial(conn, home_id, sport_m)
            _ensure_glicko2_initial(conn, away_id, sport_m)
            teams_processed.add(home_id)
            teams_processed.add(away_id)
            
            home_glicko = conn.execute(
                "SELECT * FROM glicko2_ratings WHERE team_id = ? AND sport = ?",
                (home_id, sport_m),
            ).fetchone()
            away_glicko = conn.execute(
                "SELECT * FROM glicko2_ratings WHERE team_id = ? AND sport = ?",
                (away_id, sport_m),
            ).fetchone()
            
            home_rating = float(home_glicko["rating"])
            home_rd = float(home_glicko["rd"])
            away_rating = float(away_glicko["rating"])
            away_rd = float(away_glicko["rd"])
            
            home_expected = glicko2_expected_score(home_rating, home_rd, away_rating, away_rd, home_advantage=100.0)
            away_expected = 1.0 - home_expected
            
            if score_home > score_away:
                home_actual, away_actual = 1.0, 0.0
                home_result, away_result = "win", "loss"
            elif score_home < score_away:
                home_actual, away_actual = 0.0, 1.0
                home_result, away_result = "loss", "win"
            else:
                home_actual, away_actual = 0.5, 0.5
                home_result, away_result = "draw", "draw"
            
            home_delta = 0.0
            away_delta = 0.0

            # Полноценный Glicko-2 (как в update_glicko2_for_match).
            home_vol = float(home_glicko["volatility"])
            away_vol = float(away_glicko["volatility"])
            home_new, home_new_rd, home_vol_new = glicko2_update(
                Glicko2Player(home_rating, home_rd, home_vol),
                [
                    Glicko2Match(
                        opponent_rating=away_rating,
                        opponent_rd=away_rd,
                        result=home_actual,
                        home_advantage=HOME_ADVANTAGE_POINTS,
                    )
                ],
            )
            away_new, away_new_rd, away_vol_new = glicko2_update(
                Glicko2Player(away_rating, away_rd, away_vol),
                [
                    Glicko2Match(
                        opponent_rating=home_rating,
                        opponent_rd=home_rd,
                        result=away_actual,
                        home_advantage=-HOME_ADVANTAGE_POINTS,
                    )
                ],
            )
            home_new = round(home_new, 2)
            away_new = round(away_new, 2)
            home_new_rd = round(home_new_rd, 2)
            away_new_rd = round(away_new_rd, 2)
            home_delta = round(home_new - home_rating, 2)
            away_delta = round(away_new - away_rating, 2)

            conn.execute(
                """
                UPDATE glicko2_ratings
                SET rating = ?, rd = ?, volatility = ?,
                    matches_played = matches_played + 1,
                    wins = wins + ?, draws = draws + ?, losses = losses + ?,
                    last_updated = datetime('now')
                WHERE team_id = ? AND sport = ?
                """,
                (
                    home_new,
                    home_new_rd,
                    home_vol_new,
                    1 if home_result == "win" else 0,
                    1 if home_result == "draw" else 0,
                    1 if home_result == "loss" else 0,
                    home_id,
                    sport_m,
                ),
            )
            conn.execute(
                """
                UPDATE glicko2_ratings
                SET rating = ?, rd = ?, volatility = ?,
                    matches_played = matches_played + 1,
                    wins = wins + ?, draws = draws + ?, losses = losses + ?,
                    last_updated = datetime('now')
                WHERE team_id = ? AND sport = ?
                """,
                (
                    away_new,
                    away_new_rd,
                    away_vol_new,
                    1 if away_result == "win" else 0,
                    1 if away_result == "draw" else 0,
                    1 if away_result == "loss" else 0,
                    away_id,
                    sport_m,
                ),
            )
            
            conn.execute(
                """
                INSERT INTO glicko2_rating_history
                (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["match_id"], home_id, sport_m,
                    home_rating, home_new, home_delta,
                    home_expected, home_actual,
                ),
            )
            conn.execute(
                """
                INSERT INTO glicko2_rating_history
                (match_id, team_id, sport, rating_before, rating_after, rating_delta, expected, actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["match_id"], away_id, sport_m,
                    away_rating, away_new, away_delta,
                    away_expected, away_actual,
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


# ============================================================================
# OpenSkill — система рейтинга (mu + sigma), для бинарных исходов
# ============================================================================

OPENSKILL_DEFAULT_MU: float = 25.0
OPENSKILL_DEFAULT_SIGMA: float = OPENSKILL_DEFAULT_MU / 3.0  # ~8.333
# Ширина «ничьи» (draw margin): если |score_delta| <= draw_margin — ничья.
OPENSKILL_DRAW_MARGIN: float = 0.0
# Бета (ширина «навыка»): классика ~ sigma/2
OPENSKILL_BETA: float = OPENSKILL_DEFAULT_SIGMA / 2.0


@dataclass
class OpenSkillPlayer:
    mu: float = OPENSKILL_DEFAULT_MU
    sigma: float = OPENSKILL_DEFAULT_SIGMA


def _openskill_v(x: float, t: float) -> float:
    """V-функция (v) TrueSkill/OpenSkill для одного игрока."""
    from math import erf, exp, sqrt
    if abs(t) > 30:
        pt = 1.0 if t >= 0 else 0.0
        return (pt - 1.0) * t if t < 0 else 0.0 * t
    eps = 0.0
    denom = 0.5 * (1.0 + erf((t - x) / sqrt(2.0)))
    if denom < 1e-12:
        return (t - x) if (t - x) < 0 else 0.0
    return exp(-((t - x) ** 2) / 2.0) / sqrt(2.0 * 3.141592653589793) / denom


def _openskill_w(x: float, t: float) -> float:
    """W-функция (w) TrueSkill/OpenSkill."""
    v = _openskill_v(x, t)
    return v * (v + (t - x))


def openskill_expected(mu: float, sigma: float, opp_mu: float, opp_sigma: float) -> float:
    """Вероятность победы игрока над соперником (по разнице μ)."""
    from math import erf, sqrt
    delta_mu = mu - opp_mu
    denom = sqrt(2.0 * (2.0 * OPENSKILL_BETA ** 2 + sigma ** 2 + opp_sigma ** 2))
    if denom <= 0:
        return 0.5
    return 0.5 * (1.0 + erf(delta_mu / denom))


def openskill_update(
    mu_a: float, sigma_a: float, mu_b: float, sigma_b: float,
    result_a: float,  # 1 = победа A, 0.5 = ничья, 0 = поражение A
) -> Tuple[float, float, float, float]:
    """Обновить (mu, sigma) для команды A и B по результату A.

    result_a=1 → A победил; 0.5 → ничья; 0 → A проиграл.
    Упрощённая, но устойчивая схема (Elo/Glicko-подобная) вместо полного TrueSkill:
    μ сдвигается на (факт − ожидание) * скорость, σ сужается с флором.
    Возвращает (new_mu_a, new_sigma_a, new_mu_b, new_sigma_b).
    """
    c = math.sqrt(sigma_a ** 2 + sigma_b ** 2 + 2.0 * OPENSKILL_BETA ** 2)
    # ожидание победы A
    expected = openskill_expected(mu_a, sigma_a, mu_b, sigma_b)

    # фактор уверенности: чем меньше суммарная σ, тем больше сдвиг μ
    speed = OPENSKILL_BETA ** 2 / c  # K-подобный коэффициент
    delta_a = speed * (result_a - expected)
    delta_b = -delta_a

    new_mu_a = mu_a + delta_a
    new_mu_b = mu_b + delta_b

    # σ сужается, но не ниже флора (иначе застревает в 0)
    sigma_floor = 0.5
    shrink = math.sqrt(c ** 2 / (c ** 2 + OPENSKILL_BETA ** 2))
    new_sigma_a = max(sigma_floor, sigma_a * shrink)
    new_sigma_b = max(sigma_floor, sigma_b * shrink)

    return new_mu_a, new_sigma_a, new_mu_b, new_sigma_b


def openskill_rating(mu: float, sigma: float) -> float:
    """Консервативная оценка рейтинга: μ - 3σ."""
    return mu - 3.0 * sigma


def add_openskill_tables(cursor: sqlite3.Cursor) -> None:
    """Добавляет таблицы OpenSkill в БД."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS openskill_ratings (
            team_id        INTEGER NOT NULL,
            sport          INTEGER NOT NULL,
            mu             REAL    NOT NULL DEFAULT 25.0,
            sigma          REAL    NOT NULL DEFAULT 8.3333333,
            matches_played INTEGER NOT NULL DEFAULT 0,
            wins           INTEGER NOT NULL DEFAULT 0,
            losses         INTEGER NOT NULL DEFAULT 0,
            draws          INTEGER NOT NULL DEFAULT 0,
            last_updated   TEXT    DEFAULT (datetime('now')),
            PRIMARY KEY (team_id, sport),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS openskill_rating_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id       VARCHAR(8) NOT NULL,
            team_id        INTEGER NOT NULL,
            sport          INTEGER NOT NULL,
            mu_before      REAL NOT NULL,
            mu_after       REAL NOT NULL,
            sigma_before   REAL NOT NULL,
            sigma_after    REAL NOT NULL,
            expected       REAL NOT NULL,
            actual         REAL NOT NULL,
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (match_id) REFERENCES matches(match_id),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_openskill_sport ON openskill_ratings(sport)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_openskill_mu ON openskill_ratings(mu DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_openskill_history_match ON openskill_rating_history(match_id)")


def add_team_matches_cache_tables(cursor: sqlite3.Cursor) -> None:
    """Кэш предыдущих матчей команды (feed pr_) — ОТДЕЛЬНО от таблицы matches.

    Здесь хранится история команд («последние 40 матчей до игры») для
    реконструкции. НЕ попадает в `matches`, чтобы не влиять на расчёт формы,
    skip-логику `_match_analyzed` и статистику обычных матчей.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS team_matches_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            team_key     TEXT NOT NULL,
            team_name    TEXT,
            match_id     TEXT NOT NULL,
            kickoff_ts   INTEGER,
            match_date   TEXT,
            competition  TEXT,
            home_key     TEXT,
            home_name    TEXT,
            away_key     TEXT,
            away_name    TEXT,
            home_score   INTEGER,
            away_score   INTEGER,
            is_home      INTEGER,
            UNIQUE(team_key, match_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_cache_name ON team_matches_cache(team_name)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_cache_ts ON team_matches_cache(kickoff_ts)"
    )


def _ensure_openskill_initial(conn, team_id: int, sport: int) -> None:
    row = conn.execute(
        "SELECT mu, sigma FROM openskill_ratings WHERE team_id = ? AND sport = ?",
        (team_id, sport),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO openskill_ratings (team_id, sport, mu, sigma, matches_played, wins, draws, losses)
            VALUES (?, ?, ?, ?, 0, 0, 0, 0)
            """,
            (team_id, sport, OPENSKILL_DEFAULT_MU, OPENSKILL_DEFAULT_SIGMA),
        )


def update_openskill_for_match(match_id: str) -> Optional[Dict[str, Any]]:
    """Обновить OpenSkill для завершённого матча."""
    from match_settle import is_finished_status

    with get_db_connection() as conn:
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
        if not is_finished_status(match["match_status"], match["score_home"], match["score_away"]):
            return None
        if match["score_home"] is None or match["score_away"] is None:
            return None

        sport = match["sport"]
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]
        sh = int(match["score_home"])
        sa = int(match["score_away"])

        _ensure_openskill_initial(conn, home_id, sport)
        _ensure_openskill_initial(conn, away_id, sport)

        h = conn.execute("SELECT mu, sigma FROM openskill_ratings WHERE team_id=? AND sport=?", (home_id, sport)).fetchone()
        a = conn.execute("SELECT mu, sigma FROM openskill_ratings WHERE team_id=? AND sport=?", (away_id, sport)).fetchone()
        mu_h, sig_h = float(h["mu"]), float(h["sigma"])
        mu_a, sig_a = float(a["mu"]), float(a["sigma"])

        if sh > sa:
            result_h = 1.0
            home_result, away_result = "win", "loss"
        elif sh < sa:
            result_h = 0.0
            home_result, away_result = "loss", "win"
        else:
            result_h = 0.5
            home_result, away_result = "draw", "draw"

        expected_h = openskill_expected(mu_h, sig_h, mu_a, sig_a)

        nmu_h, nsig_h, nmu_a, nsig_a = openskill_update(mu_h, sig_h, mu_a, sig_a, result_h)

        def _apply(team_id, mu_new, sig_new, result):
            conn.execute(
                """
                UPDATE openskill_ratings SET mu=?, sigma=?,
                    matches_played=matches_played+1,
                    wins=wins+?, draws=draws+?, losses=losses+?,
                    last_updated=datetime('now')
                WHERE team_id=? AND sport=?
                """,
                (round(mu_new, 6), round(sig_new, 6),
                 1 if result == "win" else 0, 1 if result == "draw" else 0, 1 if result == "loss" else 0,
                 team_id, sport),
            )
        _apply(home_id, nmu_h, nsig_h, home_result)
        _apply(away_id, nmu_a, nsig_a, away_result)

        conn.execute(
            """
            INSERT INTO openskill_rating_history
            (match_id, team_id, sport, mu_before, mu_after, sigma_before, sigma_after, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, home_id, sport, mu_h, nmu_h, sig_h, nsig_h, expected_h, result_h),
        )
        conn.execute(
            """
            INSERT INTO openskill_rating_history
            (match_id, team_id, sport, mu_before, mu_after, sigma_before, sigma_after, expected, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, away_id, sport, mu_a, nmu_a, sig_a, nsig_a, 1.0 - expected_h, 1.0 - result_h),
        )

        conn.commit()
        invalidate_cache()
        return {
            "match_id": match_id,
            "home_team": match["home_name"],
            "away_team": match["away_name"],
            "score_home": sh,
            "score_away": sa,
            "home": {"mu": mu_h, "sigma": sig_h, "rating": round(openskill_rating(mu_h, sig_h), 2)},
            "away": {"mu": mu_a, "sigma": sig_a, "rating": round(openskill_rating(mu_a, sig_a), 2)},
        }


def get_all_openskill(sport=None, limit=500, offset=0) -> Dict[str, Any]:
    where = ["1=1"]
    params: list = []
    if sport is not None:
        where.append("os.sport = ?")
        params.append(sport)
    where_sql = " AND ".join(where)
    with get_db_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM openskill_ratings os JOIN teams t ON t.id=os.team_id WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT os.team_id, t.name AS team_name, os.sport, os.mu, os.sigma,
                   os.matches_played, os.wins, os.draws, os.losses, os.last_updated,
                   (os.mu - 3.0 * os.sigma) AS rating
            FROM openskill_ratings os JOIN teams t ON t.id=os.team_id
            WHERE {where_sql}
            ORDER BY rating DESC LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


def recalculate_all_openskill(sport=None) -> Dict[str, Any]:
    """Полный пересчёт OpenSkill по истории матчей."""
    import time
    start = time.time()
    with get_db_connection() as conn:
        where = ["m.match_status IS NOT NULL", "m.score_home IS NOT NULL", "m.score_away IS NOT NULL"]
        params = []
        if sport is not None:
            where.append("m.sport = ?")
            params.append(sport)
        where_sql = " AND ".join(where)
        matches = conn.execute(
            f"""
            SELECT m.match_id, m.sport, m.score_home, m.score_away, m.home_team_id, m.away_team_id
            FROM matches m
            WHERE {where_sql}
              AND (m.match_status = 'Завершен' OR m.match_status LIKE '%овертайм%'
                   OR m.match_status LIKE '%буллит%' OR m.match_status LIKE '%тех. пораж%'
                   OR m.match_status LIKE '%неявк%')
            ORDER BY m.match_date ASC, m.id ASC
            """,
            params,
        ).fetchall()
        conn.execute("DELETE FROM openskill_ratings")
        conn.execute("DELETE FROM openskill_rating_history")
        teams = set()
        processed = 0
        for m in matches:
            m = dict(m)
            sport_m = m["sport"]
            hid, aid = m["home_team_id"], m["away_team_id"]
            sh, sa = int(m["score_home"]), int(m["score_away"])
            _ensure_openskill_initial(conn, hid, sport_m)
            _ensure_openskill_initial(conn, aid, sport_m)
            teams.add(hid)
            teams.add(aid)
            h = conn.execute("SELECT mu, sigma FROM openskill_ratings WHERE team_id=? AND sport=?", (hid, sport_m)).fetchone()
            a = conn.execute("SELECT mu, sigma FROM openskill_ratings WHERE team_id=? AND sport=?", (aid, sport_m)).fetchone()
            mu_h, sig_h = float(h["mu"]), float(h["sigma"])
            mu_a, sig_a = float(a["mu"]), float(a["sigma"])
            result_h = 1.0 if sh > sa else 0.0 if sh < sa else 0.5
            nmu_h, nsig_h, nmu_a, nsig_a = openskill_update(mu_h, sig_h, mu_a, sig_a, result_h)
            conn.execute(
                "UPDATE openskill_ratings SET mu=?, sigma=?, matches_played=matches_played+1, wins=wins+?, draws=draws+?, losses=losses+? WHERE team_id=? AND sport=?",
                (round(nmu_h, 6), round(nsig_h, 6),
                 1 if result_h == 1.0 else 0, 1 if result_h == 0.5 else 0, 1 if result_h == 0.0 else 0,
                 hid, sport_m),
            )
            conn.execute(
                "UPDATE openskill_ratings SET mu=?, sigma=?, matches_played=matches_played+1, wins=wins+?, draws=draws+?, losses=losses+? WHERE team_id=? AND sport=?",
                (round(nmu_a, 6), round(nsig_a, 6),
                 1 if result_h == 0.0 else 0, 1 if result_h == 0.5 else 0, 1 if result_h == 1.0 else 0,
                 aid, sport_m),
            )
            processed += 1
        conn.commit()
        invalidate_cache()
    return {
        "ok": True,
        "sport": sport,
        "teams_processed": len(teams),
        "matches_processed": processed,
        "duration_ms": round((time.time() - start) * 1000, 1),
    }


# ============================================================================
# MIGRATION — добавление таблиц Glicko-2
# ============================================================================

def add_glicko2_tables(cursor: sqlite3.Cursor) -> None:
    """Добавляет таблицы Glicko-2 в БД."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS glicko2_ratings (
            team_id        INTEGER NOT NULL,
            sport          INTEGER NOT NULL,
            rating         REAL    NOT NULL DEFAULT 1500,
            rd             REAL    NOT NULL DEFAULT 350,
            volatility     REAL    NOT NULL DEFAULT 0.6,
            matches_played INTEGER NOT NULL DEFAULT 0,
            wins           INTEGER NOT NULL DEFAULT 0,
            losses         INTEGER NOT NULL DEFAULT 0,
            draws          INTEGER NOT NULL DEFAULT 0,
            last_updated   TEXT    DEFAULT (datetime('now')),
            PRIMARY KEY (team_id, sport),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS glicko2_rating_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id       VARCHAR(8) NOT NULL,
            team_id        INTEGER NOT NULL,
            sport          INTEGER NOT NULL,
            rating_before  REAL NOT NULL,
            rating_after   REAL NOT NULL,
            rating_delta   REAL NOT NULL,
            expected       REAL NOT NULL,
            actual         REAL NOT NULL,
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (match_id) REFERENCES matches(match_id),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_glicko2_sport ON glicko2_ratings(sport)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_glicko2_rating ON glicko2_ratings(rating DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_glicko2_history_match ON glicko2_rating_history(match_id)"
    )


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Glicko-2 рейтинги")
    sub = parser.add_subparsers(dest="command", required=True)
    
    p_update = sub.add_parser("update", help="Обновить Glicko-2 для матча")
    p_update.add_argument("--match-id", required=True)
    
    p_recalc = sub.add_parser("recalculate", help="Пересчитать все рейтинги")
    p_recalc.add_argument("--sport", type=int, default=None)
    
    p_list = sub.add_parser("list", help="Список рейтингов")
    p_list.add_argument("--sport", type=int, default=None)

    p_os_list = sub.add_parser("openskill-list", help="Список OpenSkill рейтингов")
    p_os_list.add_argument("--sport", type=int, default=None)

    p_os_recalc = sub.add_parser("openskill-recalc", help="Пересчитать OpenSkill рейтинги")
    p_os_recalc.add_argument("--sport", type=int, default=None)

    p_all = sub.add_parser("recalculate-all", help="Пересчитать Glicko-2 и OpenSkill вместе")
    p_all.add_argument("--sport", type=int, default=None)
    
    args = parser.parse_args()
    
    if args.command == "update":
        result = update_glicko2_for_match(args.match_id)
        if result:
            print(f"[GLICKO2] Match {result['match_id']}:")
            print(f"  {result['home_team']} vs {result['away_team']}")
            print(f"  Score: {result['score_home']} - {result['score_away']}")
            print(f"  Rating before: {result['glicko2_before']}")
            print(f"  Rating after: {result['glicko2_after']}")
            print(f"  Expected: {result['expected']}")
            print(f"  Delta: {result['delta']}")
        else:
            print("[GLICKO2] No data or match not finished")
    
    elif args.command == "recalculate":
        result = recalculate_all_glicko2(args.sport)
        print(f"[GLICKO2] Recalculated: {result['teams_processed']} teams, {result['matches_processed']} matches")
        print(f"  Duration: {result['duration_ms']}ms")
    
    elif args.command == "list":
        result = get_all_glicko2(args.sport)
        print(f"\n[GLICKO2] Top {min(20, result['total'])} teams:")
        print(f"{'Rank':<6} {'Team':<25} {'Sport':<8} {'Rating':<10} {'RD':<8} {'Played':<8}")
        print("-" * 65)
        for i, item in enumerate(result["items"][:20], 1):
            print(f"{i:<6} {item['team_name']:<25} {item['sport']:<8} "
                  f"{item['rating']:<10.2f} {item['rd']:<8.2f} {item['matches_played']:<8}")

    elif args.command == "openskill-list":
        result = get_all_openskill(args.sport)
        print(f"\n[OPENSKILL] Top {min(20, result['total'])} teams:")
        print(f"{'Rank':<6} {'Team':<25} {'Sport':<8} {'Rating':<10} {'Mu':<10} {'Sigma':<8} {'Played':<8}")
        print("-" * 75)
        for i, item in enumerate(result["items"][:20], 1):
            print(f"{i:<6} {item['team_name']:<25} {item['sport']:<8} "
                  f"{item['rating']:<10.2f} {item['mu']:<10.2f} {item['sigma']:<8.2f} {item['matches_played']:<8}")

    elif args.command == "openskill-recalc":
        result = recalculate_all_openskill(args.sport)
        print(f"[OPENSKILL] Recalculated: {result['teams_processed']} teams, {result['matches_processed']} matches")
        print(f"  Duration: {result['duration_ms']}ms")

    elif args.command == "recalculate-all":
        g = recalculate_all_glicko2(args.sport)
        print(f"[GLICKO2] Recalculated: {g['teams_processed']} teams, {g['matches_processed']} matches")
        print(f"  Duration: {g['duration_ms']}ms")
        o = recalculate_all_openskill(args.sport)
        print(f"[OPENSKILL] Recalculated: {o['teams_processed']} teams, {o['matches_processed']} matches")
        print(f"  Duration: {o['duration_ms']}ms")


if __name__ == "__main__":
    main()
