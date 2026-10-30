"""Восстановить один матч из снимка БД (odds, вероятности, прогнозы).

Сеть не нужна: данные берутся из backups/db/*.db.gz. Полезно, когда матч
случайно сбросили (--reset) и заново анализировать нет возможности.

    py -3 scripts/restore_match_from_backup.py 6mdpltmc
    py -3 scripts/restore_match_from_backup.py 6mdpltmc --file matches_20261030_040714.db.gz
    py -3 scripts/restore_match_from_backup.py 6mdpltmc --dry-run
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BACKUPS = ROOT / "backups" / "db"

# Таблицы, которые восстанавливаем (все с колонкой match_id).
RESTORE_TABLES = (
    "odds",
    "outcome_probabilities",
    "goal_probabilities",
    "strategy_predictions",
    "match_stats",
    "match_missing_players",
    "moneyway",
    "whoscored_preview",
    "ml_predictions",
)

MATCH_COLUMNS = ("prediction", "match_status", "profit", "minute", "segment")


def _find_source(match_id: str, explicit: str = "") -> Path | None:
    """Найти самый свежий снимок, где у матча есть odds."""
    if explicit:
        path = BACKUPS / explicit
        return path if path.is_file() else None
    for gz in sorted(BACKUPS.glob("matches_*.db.gz"), reverse=True):
        tmp = Path(tempfile.gettempdir()) / "_probe_backup.db"
        try:
            with gzip.open(gz, "rb") as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            conn = sqlite3.connect(str(tmp))
            n = conn.execute(
                "SELECT COUNT(*) FROM odds WHERE match_id = ?", (match_id,)
            ).fetchone()[0]
            conn.close()
            if n:
                return gz
        except Exception:  # noqa: BLE001
            continue
        finally:
            tmp.unlink(missing_ok=True)
    return None


def _unpack(gz: Path) -> Path:
    tmp = Path(tempfile.gettempdir()) / f"_restore_{gz.stem}.db"
    with gzip.open(gz, "rb") as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return tmp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Восстановить матч из снимка БД без сети"
    )
    parser.add_argument("match_id", help="ID матча")
    parser.add_argument("--file", default="", help="Конкретный снимок в backups/db")
    parser.add_argument("--dry-run", action="store_true", help="Только показать")
    args = parser.parse_args()

    mid = args.match_id.strip()
    if not mid:
        print("[-] не указан match_id")
        return 2

    src_gz = _find_source(mid, args.file)
    if src_gz is None:
        print(f"[-] Не найден снимок с данными для {mid} в {BACKUPS}")
        return 1
    print(f"[*] Источник: {src_gz.name}")

    src_db = _unpack(src_gz)
    src = sqlite3.connect(str(src_db))
    try:
        src.row_factory = sqlite3.Row

        row = src.execute(
            "SELECT * FROM matches WHERE match_id = ?", (mid,)
        ).fetchone()
        if row is None:
            print(f"[-] В снимке нет матча {mid}")
            return 1

        dst = sqlite3.connect(str(get_database_path()), timeout=60)
        try:
            # 1) Поля самого матча
            cols = [c for c in MATCH_COLUMNS if c in row.keys()]
            if cols:
                sets = ", ".join(f"{c} = ?" for c in cols)
                vals = [row[c] for c in cols]
                if args.dry_run:
                    print(f"  [dry-run] matches: {dict(zip(cols, vals))}")
                else:
                    dst.execute(
                        f"UPDATE matches SET {sets} WHERE match_id = ?",
                        (*vals, mid),
                    )

            # 2) Дочерние таблицы
            total = 0
            for table in RESTORE_TABLES:
                exists = dst.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    continue
                rows = src.execute(
                    f"SELECT * FROM {table} WHERE match_id = ?", (mid,)
                ).fetchall()
                if not rows:
                    continue
                if args.dry_run:
                    print(f"  [dry-run] {table}: {len(rows)} строк")
                    total += len(rows)
                    continue
                dst.execute(f"DELETE FROM {table} WHERE match_id = ?", (mid,))
                placeholders = ", ".join("?" for _ in rows[0].keys())
                names = ", ".join(rows[0].keys())
                for r in rows:
                    dst.execute(
                        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                        tuple(r),
                    )
                print(f"  {table}: восстановлено {len(rows)}")
                total += len(rows)

            if not args.dry_run:
                dst.commit()
            print(f"[+] {'[dry-run] ' if args.dry_run else ''}всего строк: {total}")
        finally:
            dst.close()
    finally:
        # Закрываем соединение со снимком, иначе Windows не даёт удалить файл.
        try:
            src.close()
        except Exception:  # noqa: BLE001
            pass
        src_db.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
