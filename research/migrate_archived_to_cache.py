"""Однократная миграция: перенести архивные матчи (is_archived=1) из matches
в team_matches_cache (кэш истории команд), затем удалить их из matches."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from db import get_db_connection, invalidate_cache  # noqa: E402
from team_history import format_match_date  # noqa: E402


def main() -> int:
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.match_id, m.start_ts, m.score_home, m.score_away,
                   m.sport, m.is_archived,
                   th.name AS home_name, ta.name AS away_name,
                   COALESCE(c.name || ': ' || l.name, l.name, '') AS competition,
                   th.id AS home_team_id, ta.id AS away_team_id
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            LEFT JOIN leagues l ON l.id = m.league_id
            LEFT JOIN countries c ON c.id = l.country_id
            WHERE m.is_archived = 1
            """
        ).fetchall()

    if not rows:
        print("нет архивных матчей в matches")
        return 0

    # группируем по командам (team_name) для ключей кэша
    from collections import defaultdict
    by_team: dict = defaultdict(list)
    for r in rows:
        by_team[r["home_name"]].append(r)
        by_team[r["away_name"]].append(r)

    inserted = 0
    with get_db_connection() as conn:
        for r in rows:
            # в кэш пишем дважды: для домашней и гостевой команды
            for team_name, is_home in ((r["home_name"], 1), (r["away_name"], 0)):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO team_matches_cache
                    (team_key, team_name, match_id, kickoff_ts, match_date, competition,
                     home_key, home_name, away_key, away_name, home_score, away_score, is_home)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "",  # team_key неизвестен (из БД)
                        team_name,
                        r["match_id"],
                        r["start_ts"] or 0,
                        format_match_date(r["start_ts"] or 0),
                        r["competition"] or "",
                        "",
                        r["home_name"],
                        "",
                        r["away_name"],
                        r["score_home"],
                        r["score_away"],
                        is_home,
                    ),
                )
                inserted += 1

        # удаляем архивные матчи из matches
        cur = conn.execute("DELETE FROM matches WHERE is_archived = 1")
        deleted = cur.rowcount
        conn.commit()

    invalidate_cache()
    print(f"перенесено записей в кэш: {inserted}")
    print(f"удалено архивных матчей из matches: {deleted}")

    # итог
    with get_db_connection() as conn:
        left = conn.execute("SELECT COUNT(*) FROM matches WHERE is_archived=1").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        cache = conn.execute("SELECT COUNT(*) FROM team_matches_cache").fetchone()[0]
    print(f"matches: is_archived=1 → {left}, всего {total}")
    print(f"team_matches_cache: {cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
