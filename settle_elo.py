#!/usr/bin/env python
"""Batch ELO recalculation script.

Использование:
    python settle_elo.py              # пересчёт всех видов спорта
    python settle_elo.py --sport 1    # только футбол
"""

from __future__ import annotations

import argparse
import sys
import time

from db import create_database

def main() -> int:
    parser = argparse.ArgumentParser(description="Batch ELO recalculation")
    parser.add_argument("--sport", type=int, default=None, help="Sport ID (1=football, 3=basketball, etc.)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    args = parser.parse_args()

    create_database()

    from elo import recalculate_all_elo

    print(f"{'=' * 60}")
    print(f"ELO Batch Recalculation")
    print(f"Sport: {args.sport or 'ALL'}")
    print(f"{'=' * 60}")

    start = time.time()

    if args.dry_run:
        # Показываем количество матчей без пересчёта
        from db import get_db_connection
        with get_db_connection() as conn:
            where = ["m.match_status IS NOT NULL", "m.score_home IS NOT NULL", "m.score_away IS NOT NULL"]
            params = []
            if args.sport is not None:
                where.append("m.sport = ?")
                params.append(args.sport)
            where_sql = " AND ".join(where)
            count = conn.execute(
                f"SELECT COUNT(*) FROM matches m WHERE {where_sql}",
                params,
            ).fetchone()[0]
            print(f"[dry-run] Would process {count} matches")
        return 0

    result = recalculate_all_elo(sport=args.sport)

    elapsed = round((time.time() - start) / 60, 1)
    print(f"\n{'=' * 60}")
    print(f"Done! {result['matches_processed']} matches, "
          f"{result['teams_processed']} teams, "
          f"{result['duration_ms']}ms ({elapsed}min)")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
