"""Подстратегия 5 matches: анализ статистики по 5 последним матчам команд.

Собирает статистику (удары, угловые, карточки и т.д.) по 5 последним
завершённым матчам каждой команды, рассчитывает средние значения и
отклонения от нормы.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from db import get_db_connection


@dataclass
class MatchStatsRecord:
    """Статистика одного матча."""
    match_id: str
    date: str
    home_team: str
    away_team: str
    score_home: int
    score_away: int
    stats: Dict[str, float]  # stat_name -> value
    tournament: str = ""


def is_home(match: MatchStatsRecord, team_name: str) -> bool:
    """Проверяет, играет ли команда дома."""
    return match.home_team == team_name


def get_team_last_matches(
    team_name: str,
    limit: int = 5,
    before_ts: Optional[int] = None,
) -> List[MatchStatsRecord]:
    """Получить последние N завершённых матчей команды со статистикой.
    
    Args:
        team_name: Имя команды
        limit: Количество матчей
        before_ts: Если задан, возвращает только матчи ДО этого timestamp
    """
    with get_db_connection() as conn:
        # Формируем запрос с фильтром по дате
        if before_ts:
            query = """
            SELECT m.match_id, m.match_date, m.score_home, m.score_away,
                   ht.name AS home_team, at.name AS away_team,
                   COALESCE(c.name || ': ' || l.name, l.name, '') AS tournament
            FROM matches m
            JOIN teams ht ON ht.id = m.home_team_id
            JOIN teams at ON at.id = m.away_team_id
            LEFT JOIN leagues l ON l.id = m.league_id
            LEFT JOIN countries c ON c.id = l.country_id
            WHERE (ht.name = ? OR at.name = ?)
              AND m.match_status = 'Завершен'
              AND m.score_home IS NOT NULL
              AND m.match_id != 'placeholder'
              AND m.start_ts < ?
            ORDER BY m.match_date DESC
            """
            rows = conn.execute(query, (team_name, team_name, before_ts)).fetchall()
        else:
            query = """
            SELECT m.match_id, m.match_date, m.score_home, m.score_away,
                   ht.name AS home_team, at.name AS away_team,
                   COALESCE(c.name || ': ' || l.name, l.name, '') AS tournament
            FROM matches m
            JOIN teams ht ON ht.id = m.home_team_id
            JOIN teams at ON at.id = m.away_team_id
            LEFT JOIN leagues l ON l.id = m.league_id
            LEFT JOIN countries c ON c.id = l.country_id
            WHERE (ht.name = ? OR at.name = ?)
              AND m.match_status = 'Завершен'
              AND m.score_home IS NOT NULL
              AND m.match_id != 'placeholder'
            ORDER BY m.match_date DESC
            """
            rows = conn.execute(query, (team_name, team_name)).fetchall()

        # Ограничиваем количество результатов
        rows = rows[:limit]

        if not rows:
            return []

        # Для каждого матча загружаем статистику
        results = []
        for row in rows:
            match_id = row["match_id"]
            stats = get_match_stats(match_id)

            # Добавляем матч даже без статистики (статистика может отсутствовать)
            score_h = row["score_home"]
            score_a = row["score_away"]
            # Приводим к int: если dict — берём значения, если None — 0
            if isinstance(score_h, dict):
                score_h = score_h.get("home") or score_h.get("score") or 0
            if isinstance(score_a, dict):
                score_a = score_a.get("away") or score_a.get("score") or 0
            results.append(MatchStatsRecord(
                match_id=match_id,
                date=row["match_date"] or "",
                home_team=row["home_team"] or "",
                away_team=row["away_team"] or "",
                score_home=int(score_h) if score_h else 0,
                score_away=int(score_a) if score_a else 0,
                stats=stats,
                tournament=row["tournament"] or "",
            ))

        return results


def get_match_stats(match_id: str) -> Dict[str, float]:
    """Получить статистику матча из match_stats.
    
    Рекурсивно извлекает числовые значения из вложенных структур.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT stats_json FROM match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchone()

        if not row or not row["stats_json"]:
            return {}

        try:
            raw = json.loads(row["stats_json"])
            # Рекурсивно извлекаем числовые значения
            return _extract_numbers(raw)
        except (json.JSONDecodeError, TypeError):
            return {}


def _extract_numbers(obj: Any) -> Any:
    """Рекурсивно извлекает числовые значения из вложенных структур.

    Пример:
        {"Главное_Удары": {"home": 5, "away": 3}} -> {"home": 5.0, "away": 3.0}
        5 -> 5.0
        "text" -> 0.0
    """
    if isinstance(obj, (int, float)):
        return float(obj)
    elif isinstance(obj, str):
        try:
            return float(obj)
        except (ValueError, TypeError):
            return 0.0
    elif isinstance(obj, dict):
        return {k: _extract_numbers(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_extract_numbers(item) for item in obj]
    else:
        return 0.0


def _stat_to_scalar(value: Any) -> float:
    """Привести значение статистики к скаляру (для суммирования).

    Если попался dict вида {"home": 5, "away": 3} — берём home, если есть;
    если {"value": N} — берём N; иначе рекурсивно ищем первое число.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("home", "value", "total", "avg"):
            if key in value and isinstance(value[key], (int, float)):
                return float(value[key])
        # рекурсивно: первое числовое значение
        for v in value.values():
            s = _stat_to_scalar(v)
            if isinstance(s, (int, float)) and not isinstance(s, bool):
                return float(s)
        return 0.0
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    if isinstance(value, (list, tuple)):
        nums = [x for x in value if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if nums:
            return float(sum(nums) / len(nums))
        return 0.0
    return 0.0


def calculate_team_averages(team_name: str, limit: int = 5, before_ts: Optional[int] = None) -> Dict[str, Any]:
    """Рассчитать средние показатели команды по последним матчам.
    
    Args:
        team_name: Имя команды
        limit: Количество матчей
        before_ts: Если задан, возвращает только матчи ДО этого timestamp
    """
    matches = get_team_last_matches(team_name, limit, before_ts=before_ts)

    if not matches:
        return {"team_name": team_name, "matches_count": 0}

    # Считаем средние по каждой статистике
    stat_sums: Dict[str, List[float]] = {}
    total_goals_scored = 0
    total_goals_conceded = 0
    wins = draws = losses = 0

    for match in matches:
        # Определяем, играет ли команда дома или в гостях
        home_team_flag = (match.home_team == team_name)

        for stat_name, value in match.stats.items():
            if stat_name not in stat_sums:
                stat_sums[stat_name] = []
            stat_sums[stat_name].append(_stat_to_scalar(value))

        # Голы
        if home_team_flag:
            total_goals_scored += match.score_home
            total_goals_conceded += match.score_away
        else:
            total_goals_scored += match.score_away
            total_goals_conceded += match.score_home

        # Результаты
        if home_team_flag:
            if match.score_home > match.score_away:
                wins += 1
            elif match.score_home == match.score_away:
                draws += 1
            else:
                losses += 1
        else:
            if match.score_away > match.score_home:
                wins += 1
            elif match.score_away == match.score_home:
                draws += 1
            else:
                losses += 1

    # Рассчитываем средние
    averages = {}
    for stat_name, values in stat_sums.items():
        averages[stat_name] = sum(values) / len(values) if values else 0.0

    return {
        "team_name": team_name,
        "matches_count": len(matches),
        "matches": [
            {
                "match_id": m.match_id,
                "date": m.date,
                "tournament": m.tournament,
                "opponent": m.away_team if is_home(m, team_name) else m.home_team,
                "venue": "Дома" if is_home(m, team_name) else "Гости",
                "score": f"{m.score_home}:{m.score_away}",
                "stats": m.stats,
            }
            for m in matches
        ],
        "averages": averages,
        "total_goals_scored": total_goals_scored,
        "total_goals_conceded": total_goals_conceded,
        "avg_goals_scored": total_goals_scored / len(matches) if matches else 0,
        "avg_goals_conceded": total_goals_conceded / len(matches) if matches else 0,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_rate": wins / len(matches) if matches else 0,
    }


def calculate_deviations(
    team_stats: Dict[str, Any],
    league_averages: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Рассчитать отклонения от лиговых средних."""
    if not team_stats or not league_averages:
        return {}

    deviations = {}
    for stat_name, avg_value in team_stats.get("averages", {}).items():
        league_avg = league_averages.get(stat_name)
        if league_avg and league_avg > 0:
            # Процентное отклонение
            deviation = ((avg_value - league_avg) / league_avg) * 100
            deviations[stat_name] = round(deviation, 1)

    return deviations


def analyze_team_form(team_name: str, limit: int = 5, before_ts: Optional[int] = None) -> Dict[str, Any]:
    """Полный анализ формы команды по 5 последним матчам.
    
    Args:
        team_name: Имя команды
        limit: Количество матчей
        before_ts: Если задан, возвращает только матчи ДО этого timestamp
    """
    team_stats = calculate_team_averages(team_name, limit, before_ts=before_ts)

    if team_stats.get("matches_count", 0) == 0:
        return {
            "team_name": team_name,
            "status": "no_data",
            "message": "Нет данных о завершённых матчах",
        }

    # Рассчитываем отклонения
    deviations = calculate_deviations(team_stats)

    # Определяем тренды
    trends = detect_trends(team_stats, deviations)

    return {
        "team_name": team_name,
        "status": "ok",
        "matches_count": team_stats["matches_count"],
        "matches": team_stats.get("matches", []),
        "averages": team_stats["averages"],
        "goals": {
            "scored": team_stats["avg_goals_scored"],
            "conceded": team_stats["avg_goals_conceded"],
        },
        "results": {
            "wins": team_stats["wins"],
            "draws": team_stats["draws"],
            "losses": team_stats["losses"],
            "win_rate": team_stats["win_rate"],
        },
        "deviations": deviations,
        "trends": trends,
    }


def detect_trends(team_stats: Dict[str, Any], deviations: Dict[str, float]) -> Dict[str, str]:
    """Определяет тренды на основе отклонений."""
    trends = {}

    # Атакующий потенциал
    shots_on_target = deviations.get("Главное_Удары в створ", 0)
    if shots_on_target > 15:
        trends["attack"] = "strong"
    elif shots_on_target < -15:
        trends["attack"] = "weak"
    else:
        trends["attack"] = "normal"

    # Контроль мяча
    possession = deviations.get("Главное_Владение мячом", 0)
    if possession > 10:
        trends["possession"] = "dominant"
    elif possession < -10:
        trends["possession"] = "weak"
    else:
        trends["possession"] = "normal"

    # Дисциплина
    yellow_cards = deviations.get("Главное_Желтые карточки", 0)
    if yellow_cards > 20:
        trends["discipline"] = "aggressive"
    elif yellow_cards < -20:
        trends["discipline"] = "clean"
    else:
        trends["discipline"] = "normal"

    return trends


def save_team_stats_to_db(team_name: str, analysis: Dict[str, Any]) -> None:
    """Сохраняет анализ формы команды в БД."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO team_form_stats (
                team_name, stats_json, fetched_at
            ) VALUES (?, ?, datetime('now'))
            ON CONFLICT(team_name) DO UPDATE SET
                stats_json = excluded.stats_json,
                fetched_at = excluded.fetched_at
            """,
            (team_name, json.dumps(analysis, ensure_ascii=False)),
        )
        conn.commit()


def get_team_form_from_db(team_name: str) -> Dict[str, Any] | None:
    """Получает сохранённый анализ формы команды из БД."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT stats_json FROM team_form_stats WHERE team_name = ?",
            (team_name,),
        ).fetchone()

        if not row:
            return None

        try:
            return json.loads(row["stats_json"])
        except (json.JSONDecodeError, TypeError):
            return None
