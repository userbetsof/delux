"""Заполнить match_snapshot таблицей для матчей, у которых она пустая.

Берёт восстановленную таблицу из кэша сезона (season_standings_cache) или
из самого снимка (старые записи), и пишет standards_json. Нужно для матчей,
проанализированных до появления кэша: у них таблица потерялась, и повторный
анализ без сети не может её восстановить.

    py -3 scripts/backfill_snapshot_tables.py --dry-run
    py -3 scripts/backfill_snapshot_tables.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _all_cached(conn: sqlite3.Connection) -> dict[str, str]:
    """match_id -> standings_json из кэша сезона."""
    out: dict[str, str] = {}
    for row in conn.execute(
        "SELECT match_id, standings_json FROM season_standings_cache "
        "WHERE standings_json IS NOT NULL AND TRIM(standings_json) <> ''"
    ):
        out.setdefault(row[0], row[1])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(get_database_path()), timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        targets = [
            r["match_id"]
            for r in conn.execute(
                "SELECT match_id FROM match_snapshot "
                "WHERE standings_json IS NULL OR TRIM(standings_json) = ''"
            )
        ]
        print(f"снимков без таблицы: {len(targets)}")
        cached = _all_cached(conn)
        print(f"в кэше сезона: {len(cached)} матчей")

        filled = 0
        missing = 0
        for mid in targets:
            raw = cached.get(mid)
            if not raw:
                missing += 1
                continue
            try:
                data = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                missing += 1
                continue
            if not isinstance(data, dict) or not data.get("overall"):
                missing += 1
                continue
            if not args.dry_run:
                conn.execute(
                    "UPDATE match_snapshot SET standings_json = ? WHERE match_id = ?",
                    (raw, mid),
                )
            filled += 1

        if args.dry_run:
            print(f"[dry-run] можно заполнить: {filled}, без данных: {missing}")
            return 0

        conn.commit()
        print(f"[+] заполнено: {filled}")
        if missing:
            print(f"    без данных в кэше: {missing} (нужен онлайн-анализ)")
        left = conn.execute(
            "SELECT COUNT(*) FROM match_snapshot "
            "WHERE standings_json IS NULL OR TRIM(standings_json) = ''"
        ).fetchone()[0]
        print(f"    осталось без таблицы: {left}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
