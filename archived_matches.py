"""Архивные матчи: перенос истории команд (pr_ feed) в формат рабочей БД matches.db.

Цель: сохранить последние N матчей команды ТАК ЖЕ, как обычные матчи в
matches.db (таблица matches), но с is_archived=1 и только теми полями,
которые доступны по историческим данным (счёт, дата, команды, лига, спорт).

Тестовая среда — `test_archive.db` (та же схема, что у matches.db).
Перенос в рабочую БД = сменить `--db` на `matches.db` (или DATABASE_PATH).
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List

from flashscore_feed import clean_team_name
from team_history import fetch_team_matches, format_match_date

TEST_DB = "test_archive.db"


def _normalize_score(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def insert_archived_matches(matches: List[Dict[str, Any]], sport: int) -> int:
    """Вставить матчи как архивные в текущую БД (схема matches.db).

    Возвращает число записанных матчей. INSERT OR IGNORE — не перезаписывает
    матчи, которые уже есть (например, обычные), а только дополняет архив.
    """
    from db import (
        get_db_connection,
        insert_or_get_country,
        insert_or_get_league,
        insert_or_get_team,
        parse_league,
    )

    saved = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for m in matches:
            match_id = (m.get("match_id") or "").strip()
            # Суффиксы «(Анг)»/«(Гер)» в товарищеских матчах убираем — как в рабочей БД
            home_name = clean_team_name(m.get("home_name") or "")
            away_name = clean_team_name(m.get("away_name") or "")
            if not match_id or not home_name or not away_name:
                continue

            country_name, league_name = parse_league(m.get("competition") or "")
            country_id = insert_or_get_country(cursor, country_name)
            league_id = insert_or_get_league(cursor, league_name, country_id)
            home_id = insert_or_get_team(cursor, home_name)
            away_id = insert_or_get_team(cursor, away_name)

            cursor.execute(
                """
                INSERT OR IGNORE INTO matches
                (match_id, match_date, start_ts, league_id, home_team_id, away_team_id,
                 match_status, score_home, score_away, sport, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, 'Завершен', ?, ?, ?, 1)
                """,
                (
                    match_id,
                    format_match_date(m.get("kickoff_ts") or 0),
                    m.get("kickoff_ts") or 0,
                    league_id,
                    home_id,
                    away_id,
                    _normalize_score(m.get("home_score")),
                    _normalize_score(m.get("away_score")),
                    int(sport),
                ),
            )
            saved += cursor.rowcount
        conn.commit()
    return saved


def write_match(match: Dict[str, Any], *, is_archived: int = 1) -> bool:
    """Записать один матч в рабочую БД (matches.db).

    `match` — словарь с уже разрешёнными полями: match_id, match_date,
    start_ts, league_id, home_team_id, away_team_id, score_home, score_away,
    sport, match_status (по умолчанию 'Завершен').
    """
    from db import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO matches
            (match_id, match_date, start_ts, league_id, home_team_id, away_team_id,
             match_status, score_home, score_away, sport, is_archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match["match_id"],
                match["match_date"],
                match.get("start_ts"),
                match["league_id"],
                match["home_team_id"],
                match["away_team_id"],
                match.get("match_status", "Завершен"),
                match.get("score_home", 0),
                match.get("score_away", 0),
                match.get("sport", 1),
                is_archived,
            ),
        )
        conn.commit()
    return True


def archive_team_matches(
    team_key: str,
    team_name: str = "",
    *,
    country: int = 81,
    sport: int = 1,
    limit: int = 40,
    db_path: str = TEST_DB,
) -> int:
    """Спарсить последние `limit` матчей команды и записать как архивные в db_path."""
    from db import create_database, database_path

    matches = fetch_team_matches(team_key, country=country, sport=sport, limit=limit)
    with database_path(db_path):
        create_database()
        saved = insert_archived_matches(matches, sport)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Архивные матчи команды (pr_ feed → matches.db-схема)")
    parser.add_argument("--team-key", required=True, help="Flashscore ключ команды")
    parser.add_argument("--team-name", default="", help="Название команды")
    parser.add_argument("--country-id", type=int, default=198, help="ID страны (198=Англия, 81=Германия)")
    parser.add_argument("--sport", type=int, default=1, help="Вид спорта")
    parser.add_argument("--limit", type=int, default=40, help="Сколько последних матчей")
    parser.add_argument("--db", default=TEST_DB, help="Путь к БД (по умолчанию test_archive.db)")
    args = parser.parse_args()

    saved = archive_team_matches(
        args.team_key,
        args.team_name,
        country=args.country_id,
        sport=args.sport,
        limit=args.limit,
        db_path=args.db,
    )
    print(f"[OK] Записано {saved} архивных матчей в {args.db}")


if __name__ == "__main__":
    main()
