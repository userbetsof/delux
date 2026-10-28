"""Проставить result/profit по прогнозам завершённых матчей и matches.profit.

Нужно для матчей, проанализированных до появления авто-расчёта прибыли:
у них strategy_predictions.result/profit = NULL и matches.profit = 0.

    py -3 scripts/settle_finished_matches.py --dry-run
    py -3 scripts/settle_finished_matches.py
    py -3 scripts/settle_finished_matches.py --settled-only
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--settled-only",
        action="store_true",
        help="Только матчи, где есть прогнозы, но result не проставлен",
    )
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT DISTINCT m.match_id
            FROM matches m
            JOIN strategy_predictions sp ON sp.match_id = m.match_id
            WHERE m.match_status = 'Завершен'
              AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
        """
        if args.settled_only:
            sql += " AND sp.result IS NULL"
        sql += " ORDER BY m.start_ts DESC"
        ids = [r["match_id"] for r in conn.execute(sql)]
    finally:
        conn.close()

    if args.limit:
        ids = ids[: args.limit]
    print(f"завершённых матчей с прогнозами: {len(ids)}")
    if args.dry_run:
        print("  пример:", ", ".join(ids[:10]))
        return 0

    from match_analysis import settle_match_predictions

    ok = fail = 0
    total = 0.0
    for i, mid in enumerate(ids, 1):
        try:
            res = settle_match_predictions(mid)
            if res:
                ok += 1
                total += float(res["total"])
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(ids)}] {mid}: FAIL {type(exc).__name__}: {exc}")

    print(f"\nготово: матчей {ok}, ошибок {fail}, суммарная прибыль {total:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
