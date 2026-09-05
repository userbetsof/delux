"""Нормализация дат в matches.match_date и match_queue.date_match → YYYY.MM.DD HH:MM."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from date_utils import normalize_match_date  # noqa: E402
from db import get_database_path  # noqa: E402


def normalize_table(conn: sqlite3.Connection, table: str, column: str) -> tuple[int, int]:
    rows = conn.execute(f"SELECT rowid, {column} FROM {table}").fetchall()
    changed = skipped = 0
    for rowid, raw in rows:
        new_val = normalize_match_date(raw)
        if not new_val:
            skipped += 1
            continue
        if str(raw or "").strip() == new_val:
            continue
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE rowid = ?", (new_val, rowid))
        changed += 1
    return changed, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize match dates to YYYY.MM.DD HH:MM")
    parser.add_argument("--db", default="", help="Путь к matches.db")
    args = parser.parse_args()
    path = args.db.strip() or get_database_path()

    conn = sqlite3.connect(path)
    try:
        m_changed, m_skipped = normalize_table(conn, "matches", "match_date")
        q_changed, q_skipped = normalize_table(conn, "match_queue", "date_match")
        conn.commit()
    finally:
        conn.close()

    print(f"matches: updated={m_changed} skipped_empty={m_skipped}")
    print(f"match_queue: updated={q_changed} skipped_empty={q_skipped}")
    print(f"db: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
