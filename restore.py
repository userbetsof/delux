"""Восстановление БД из снимка бэкапа.

Берёт самый свежий (или указанный) файл из backups/db/, распаковывает и
подменяет рабочую БД. Перед подменой текущая БД сохраняется на всякий случай.

    py -3 restore.py --list              # что есть в бэкапах
    py -3 restore.py --dry-run           # показать, что будет сделано
    py -3 restore.py                     # восстановить последний снимок
    py -3 restore.py --file matches_20261028_121703.db.gz
    py -3 restore.py --from-git <tag>    # только код (git checkout)

ВАЖНО: перед восстановлением закройте админку и анализ — файл БД будет
заменён, открытые соединения потеряют консистентность.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH") or (ROOT / "matches.db"))
BACKUP_DIR = ROOT / "backups" / "db"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _fmt_mb(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} МБ"


def list_backups() -> list[Path]:
    if not BACKUP_DIR.is_dir():
        return []
    return sorted(
        (p for p in BACKUP_DIR.glob("matches_*.db*") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def cmd_list() -> int:
    items = list_backups()
    if not items:
        print(f"Снимков нет: {BACKUP_DIR}")
        return 1
    print(f"Снимки в {BACKUP_DIR.relative_to(ROOT)}:")
    for i, path in enumerate(items, 1):
        stat = path.stat()
        when = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {i:2}. {path.name:36} {_fmt_mb(stat.st_size):>9}  {when}")
    return 0


def _unpack(path: Path, target: Path) -> Path:
    """Распаковать .gz (или скопировать .db) во временный файл."""
    tmp = target.with_name(target.name + ".restore-tmp")
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        shutil.copy2(path, tmp)
    return tmp


def _verify(path: Path) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(str(path), timeout=30)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return False, f"integrity_check: {integrity}"
            fk = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk:
                return False, f"FK violations: {len(fk)}"
            matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        finally:
            conn.close()
        return True, f"ok, матчей {matches}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def cmd_file(backup: Path, *, dry_run: bool) -> int:
    """Восстановить снимок вместо текущей БД."""
    if not backup.is_file():
        print(f"[!] файл не найден: {backup}")
        return 1
    print(f"Источник: {backup.name} ({_fmt_mb(backup.stat().st_size)})")

    tmp = _unpack(backup, DB_PATH)
    try:
        ok, detail = _verify(tmp)
        if not ok:
            print(f"[!] снимок повреждён: {detail}")
            return 1
        print(f"Проверка снимка: {detail}")

        if dry_run:
            print("[dry-run] восстановление не выполнено")
            return 0

        # Сохраняем текущую БД перед подменой (консистентно, через VACUUM INTO).
        if DB_PATH.is_file():
            safety = BACKUP_DIR / f"before-restore_{datetime.now():%Y%m%d_%H%M%S}.db"
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            try:
                conn = sqlite3.connect(str(DB_PATH), timeout=30)
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.execute(f"VACUUM INTO '{str(safety).replace(chr(39), chr(39)*2)}'")
                finally:
                    conn.close()
                print(f"Текущая БД сохранена: {safety.name} ({_fmt_mb(safety.stat().st_size)})")
            except Exception as exc:  # noqa: BLE001
                print(f"[!] не удалось сохранить текущую БД: {exc}")
                return 1

        # Удаляем WAL/SHM — иначе они применятся поверх восстановленного файла.
        for suffix in ("-wal", "-shm"):
            side = Path(str(DB_PATH) + suffix)
            if not side.exists():
                continue
            try:
                side.unlink()
                print(f"Удалён {side.name}")
            except PermissionError:
                print(
                    f"[!] Файл {side.name} занят другим процессом.\n"
                    f"    Закройте админку (Nuxt на :3000), анализ и другие\n"
                    f"    процессы, работающие с matches.db, и повторите."
                )
                return 1

        try:
            shutil.move(str(tmp), str(DB_PATH))
        except PermissionError:
            print(
                "[!] matches.db занят другим процессом.\n"
                "    Закройте админку и анализ, затем повторите восстановление."
            )
            return 1
        print(f"[+] БД восстановлена: {DB_PATH.name} ({_fmt_mb(DB_PATH.stat().st_size)})")
        return 0
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def cmd_git_checkout(tag: str) -> int:
    res = subprocess.run(
        ["git", "checkout", tag],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        print(f"[!] git checkout {tag}: {res.stderr.strip()}")
        return 1
    print(f"[+] Код переключён на {tag}")
    print("    Вернуться на актуальную ветку: git checkout main")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Восстановление БД из бэкапа")
    parser.add_argument("--list", action="store_true", help="Показать снимки")
    parser.add_argument("--file", default="", help="Имя снимка в backups/db/")
    parser.add_argument("--dry-run", action="store_true", help="Только проверить")
    parser.add_argument("--from-git", default="", help="Переключить код на git-тег")
    args = parser.parse_args()

    if args.list:
        return cmd_list()
    if args.from_git:
        return cmd_git_checkout(args.from_git)

    if args.file:
        candidate = BACKUP_DIR / args.file
        if not candidate.is_file():
            candidate = Path(args.file)
        return cmd_file(candidate, dry_run=args.dry_run)

    items = list_backups()
    if not items:
        print(f"[!] Снимков нет в {BACKUP_DIR}")
        return 1
    return cmd_file(items[0], dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
