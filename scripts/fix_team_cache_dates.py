"""Починить team_matches_cache: проставить match_date из kickoff_ts.

Причина: research/migrate_archived_to_cache.py писал match_date = "" с
комментарием «не критичен». Из-за этого в «последних матчах» на странице
матча колонка «Дата» была пустой.

    py -3 scripts/fix_team_cache_dates.py --dry-run
    py -3 scripts/fix_team_cache_dates.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402
from team_history import format_match_date  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, kickoff_ts FROM team_matches_cache "
            "WHERE (match_date IS NULL OR TRIM(match_date) = '') "
            "AND kickoff_ts IS NOT NULL AND kickoff_ts > 0"
        ).fetchall()
        print(f"строк без даты: {len(rows)}")

        fixed = 0
        for row in rows:
            date_str = format_match_date(int(row["kickoff_ts"]))
            if not date_str:
                continue
            if not args.dry_run:
                conn.execute(
                    "UPDATE team_matches_cache SET match_date = ? WHERE id = ?",
                    (date_str, row["id"]),
                )
            fixed += 1
            if fixed <= 3:
                print(f"  id={row['id']} ts={row['kickoff_ts']} -> {date_str}")

        if args.dry_run:
            print(f"[dry-run] было бы обновлено: {fixed}")
        else:
            conn.commit()
            print(f"[+] обновлено: {fixed}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
