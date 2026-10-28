"""Проставляет кф в прогнозы стратегий по таблице odds (бэкфилл).

    py -3 fill_prediction_odds.py                # все матчи
    py -3 fill_prediction_odds.py --dry-run      # только показать
    py -3 fill_prediction_odds.py --match-id KdLPRx82
    py -3 fill_prediction_odds.py --overwrite    # перезаписать и уже стоящие кф
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

from db import get_database_path  # noqa: E402
from prediction_odds import fill_prediction_odds  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Кф в прогнозы стратегий")
    parser.add_argument("--db", default="", help="путь к SQLite (по умолчанию matches.db)")
    parser.add_argument("--match-id", default="", help="только один матч")
    parser.add_argument("--overwrite", action="store_true", help="перезаписать существующие кф")
    parser.add_argument("--dry-run", action="store_true", help="не писать в БД")
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path(args.db or None))
    conn.row_factory = sqlite3.Row
    try:
        changes = fill_prediction_odds(
            conn,
            args.match_id or None,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    finally:
        conn.close()

    by_strategy: dict[int, int] = {}
    for _mid, sid, _pred, _val in changes:
        by_strategy[sid] = by_strategy.get(sid, 0) + 1

    print(f"[+] {'найдено' if args.dry_run else 'проставлено'} кф: {len(changes)}")
    for sid in sorted(by_strategy):
        print(f"    стратегия #{sid}: {by_strategy[sid]}")
    if args.match_id:
        for mid, sid, pred, val in changes:
            print(f"    {mid} #{sid} {pred} @ {val:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
