"""Сброс всех рейтингов к изначальному состоянию.

Обнуляет ELO, Glicko-2, OpenSkill и их историю — рейтинги возвращаются к
стартовым значениям, как у новых команд. После сброса рейтинги можно либо
пересчитать заново (`py -3 ratings.py recalculate-all` + `elo.py recalculate`),
либо накапливать по мере анализа матчей.

    py -3 scripts/reset_ratings.py --dry-run
    py -3 scripts/reset_ratings.py
    py -3 scripts/reset_ratings.py --no-history   # оставить историю
    py -3 scripts/reset_ratings.py --delete       # удалить строки (не обнулять)
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402

# Стартовые значения берём из самих модулей, чтобы не расходиться с логикой.
def _initial_values() -> dict:
    import elo
    import ratings

    return {
        "team_elo_ratings": {
            "rating": elo.INITIAL_RATING,
        },
        "glicko2_ratings": {
            "rating": ratings.GLICKO2_INITIAL_RATING,
            "rd": ratings.GLICKO2_INITIAL_RD,
            "volatility": ratings.GLICKO2_VOLATILITY,
        },
        "openskill_ratings": {
            "mu": ratings.OPENSKILL_DEFAULT_MU,
            "sigma": ratings.OPENSKILL_DEFAULT_SIGMA,
        },
    }


# Общие для всех рейтинговых таблиц счётчики.
_COUNTERS = ("matches_played", "wins", "losses", "draws")

HISTORY_TABLES = (
    "elo_rating_history",
    "glicko2_rating_history",
    "openskill_rating_history",
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Сброс рейтингов к исходному состоянию")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет сделано")
    parser.add_argument("--no-history", action="store_true", help="Не очищать историю рейтингов")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Удалить строки рейтингов вместо обнуления (создадутся заново при анализе)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    try:
        initial = _initial_values()

        print("=== Рейтинги")
        for table, values in initial.items():
            if not _table_exists(conn, table):
                print(f"  {table}: таблицы нет — пропуск")
                continue
            cols = _columns(conn, table)
            total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

            if args.delete:
                if not args.dry_run:
                    conn.execute(f'DELETE FROM "{table}"')
                print(f"  {table}: удалено {total} строк")
                continue

            # Обнуляем счётчики и ставим стартовые значения по тем полям, что есть.
            sets, params = [], []
            for col, val in values.items():
                if col in cols:
                    sets.append(f"{col} = ?")
                    params.append(val)
            for col in _COUNTERS:
                if col in cols:
                    sets.append(f"{col} = 0")
            if "last_updated" in cols:
                sets.append("last_updated = datetime('now', 'localtime')")
            if not sets:
                print(f"  {table}: нет подходящих колонок — пропуск")
                continue
            if not args.dry_run:
                conn.execute(f'UPDATE "{table}" SET {", ".join(sets)}', params)
            desc = ", ".join(f"{k}={v}" for k, v in values.items())
            print(f"  {table}: сброшено {total} строк ({desc}, счётчики=0)")

        if not args.no_history:
            print("=== История рейтингов")
            for table in HISTORY_TABLES:
                if not _table_exists(conn, table):
                    continue
                total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                if not args.dry_run:
                    conn.execute(f'DELETE FROM "{table}"')
                print(f"  {table}: удалено {total} строк")

        if args.dry_run:
            print("\n[dry-run] изменения не записаны")
            return 0

        conn.commit()
        print("\n[+] Готово. Рейтинги в исходном состоянии.")
        print("    Пересчитать заново:  py -3 ratings.py recalculate-all")
        print("    (ELO пересчитывается при следующем анализе матча)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
