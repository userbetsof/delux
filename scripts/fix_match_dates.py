"""Починить matches: проставить match_date / start_ts из dc_-фида.

Причина: для части матчей расчёт не дал start_ts, и в matches остались
пустые match_date и start_ts. Из-за этого «Последние матчи» на странице
матча (team_form_stats ← matches) показывали пустую дату, а фильтр по
start_ts отбрасывал матч.

    py -3 scripts/fix_match_dates.py --dry-run
    py -3 scripts/fix_match_dates.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402
from feed_ids import match_start_ts  # noqa: E402
from team_history import format_match_date  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT match_id, sport, match_date, start_ts FROM matches "
            "WHERE (match_date IS NULL OR TRIM(match_date) = '') "
            "   OR start_ts IS NULL OR start_ts = 0 "
            "ORDER BY id DESC"
        ).fetchall()
        if args.limit:
            rows = rows[: args.limit]
        print(f"матчей без даты/start_ts: {len(rows)}")

        fixed = 0
        for row in rows:
            sport = int(row["sport"] or 1)
            ts = match_start_ts(row["match_id"], sport=sport)
            if not ts:
                print(f"  [!] {row['match_id']}: нет kickoff в dc_")
                continue
            date_str = format_match_date(ts)
            if not args.dry_run:
                conn.execute(
                    "UPDATE matches SET start_ts = ?, match_date = ? WHERE match_id = ?",
                    (ts, date_str, row["match_id"]),
                )
            fixed += 1
            if fixed <= 5:
                print(f"  {row['match_id']}: start_ts={ts} date={date_str}")

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
