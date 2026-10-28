"""Слить лиги, попавшие под страну 'Unknown', с их настоящими лигами.

Причина: db.parse_league возвращает ('Unknown', league), если в строке лиги
нет ": " — так бывает, когда расчёт не дал league. В итоге «Примера» (id 31)
висит под Unknown рядом с настоящей «Примерой» (id 4, ИСПАНИЯ), и в
«последних матчах» турнир показывается как "Unknown: Примера".

Страна определяется по командам: у команд из Unknown-лиги почти всегда есть
матчи в лиге с тем же названием и нормальной страной.

    py -3 scripts/merge_unknown_leagues.py --dry-run
    py -3 scripts/merge_unknown_leagues.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402

UNKNOWN_ID = 11


def find_target(conn: sqlite3.Connection, league_id: int, league_name: str) -> int:
    """Найти настоящую лигу (то же имя, не Unknown) по командам матчей."""
    teams = [
        r["name"]
        for r in conn.execute(
            "SELECT DISTINCT t.name FROM matches m "
            "JOIN teams t ON t.id IN (m.home_team_id, m.away_team_id) "
            "WHERE m.league_id = ?",
            (league_id,),
        )
    ]
    votes: Counter[int] = Counter()
    for team in teams:
        for row in conn.execute(
            "SELECT l.id, COUNT(*) AS n FROM matches m "
            "JOIN teams t ON t.id IN (m.home_team_id, m.away_team_id) "
            "JOIN leagues l ON l.id = m.league_id "
            "WHERE t.name = ? AND l.country_id <> ? AND l.name = ? "
            "GROUP BY l.id",
            (team, UNKNOWN_ID, league_name),
        ):
            votes[row["id"]] += row["n"]
    if not votes:
        return 0
    return votes.most_common(1)[0][0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        leagues = conn.execute(
            "SELECT l.id, l.name, COUNT(m.id) AS n FROM leagues l "
            "LEFT JOIN matches m ON m.league_id = l.id "
            "WHERE l.country_id = ? GROUP BY l.id ORDER BY n DESC",
            (UNKNOWN_ID,),
        ).fetchall()

        moved = 0
        for league in leagues:
            target = find_target(conn, league["id"], league["name"])
            if not target:
                print(
                    f"  [{league['name']}] матчей {league['n']}: "
                    f"настоящая лига не найдена — пропуск"
                )
                continue
            row = conn.execute(
                "SELECT l.name, c.name AS country FROM leagues l "
                "JOIN countries c ON c.id = l.country_id WHERE l.id = ?",
                (target,),
            ).fetchone()
            print(
                f"  [{league['name']}] id={league['id']} матчей {league['n']} "
                f"-> id={target} ({row['country']}: {row['name']})"
            )
            if not args.dry_run:
                conn.execute(
                    "UPDATE matches SET league_id = ? WHERE league_id = ?",
                    (target, league["id"]),
                )
                # Переиспользуем настоящую лигу; пустую Unknown-запись удаляем,
                # иначе мешает UNIQUE(name, country_id).
                left = conn.execute(
                    "SELECT COUNT(*) FROM matches WHERE league_id = ?",
                    (league["id"],),
                ).fetchone()[0]
                if left == 0:
                    conn.execute("DELETE FROM leagues WHERE id = ?", (league["id"],))
            moved += 1

        if args.dry_run:
            print(f"\n[dry-run] было бы слито: {moved}")
        else:
            conn.commit()
            print(f"\n[+] слито: {moved}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
