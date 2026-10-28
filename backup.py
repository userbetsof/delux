"""Ручной бэкап: git-коммит кода + согласованная копия БД.

Что делает:
  1. Проверяет БД на целостность (PRAGMA integrity_check).
  2. Делает консистентный снимок SQLite через VACUUM INTO (безопасно при WAL
     и открытых соединениях — не требует останавливать админку).
  3. Кладёт снимок в backups/db/matches_YYYYMMDD_HHMMSS.db, сжимает в .gz
     и удаляет старые копии сверх --keep.
  4. Опционально коммитит изменения кода в git и ставит тег.

Код и БД разделены намеренно: .db в .gitignore (123 МБ в git — плохая идея),
поэтому база бэкапится отдельными файлами, а код — git-коммитом с тегом,
чтобы версия БД была привязана к конкретному состоянию кода.

    py -3 backup.py                    # БД + git-коммит (спросит сообщение)
    py -3 backup.py --db-only          # только БД
    py -3 backup.py --git-only         # только git
    py -3 backup.py -m "текст"         # сообщение коммита без вопроса
    py -3 backup.py --keep 30          # сколько БД-копий хранить
    py -3 backup.py --tag              # ещё и git-тег backup-YYYYMMDD-HHMMSS
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

# Консоль Windows по умолчанию cp1251 — кириллица и «→» падают.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _fmt_mb(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} МБ"


# --------------------------------------------------------------------- БД
def check_db_integrity(db_path: Path) -> tuple[bool, str]:
    """PRAGMA integrity_check + foreign_key_check.

    Важно: соединение открывается ОБЫЧНЫМ (read-write), не read-only.
    В режиме WAL read-only соединение не видит неhекпоинченный лог и может
    показать «нарушения», которых нет в реальной базе.
    """
    if not db_path.is_file():
        return False, f"файл не найден: {db_path}"
    try:
        conn = sqlite3.connect(str(db_path), timeout=60)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return False, f"integrity_check: {integrity}"
            fk = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk:
                tables = sorted({r[0] for r in fk})
                return False, f"нарушено внешних ключей: {len(fk)} ({', '.join(tables)})"
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
            if quick != "ok":
                return False, f"quick_check: {quick}"
        finally:
            conn.close()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def make_db_backup(db_path: Path, out_dir: Path, *, compress: bool = True) -> Path:
    """Консистентный снимок БД через VACUUM INTO.

    VACUUM INTO даёт корректную копию даже при активном WAL и открытых
    соединениях — не нужно останавливать админку или анализ.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"matches_{_stamp()}.db"
    # Обычное соединение (не read-only): в WAL-режиме read-only снимок
    # не увидел бы ещё не сhекпоинченный лог.
    conn = sqlite3.connect(str(db_path), timeout=60)
    try:
        target = str(raw).replace("'", "''")
        conn.execute(f"VACUUM INTO '{target}'")
    finally:
        conn.close()

    if not compress:
        return raw

    gz = raw.with_suffix(".db.gz")
    with open(raw, "rb") as src, gzip.open(gz, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    raw.unlink(missing_ok=True)
    return gz


def prune_backups(out_dir: Path, keep: int) -> list[Path]:
    """Удалить старые копии, оставив `keep` самых новых."""
    if keep <= 0:
        return []
    files = sorted(
        (p for p in out_dir.glob("matches_*.db*") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )
    removed = []
    for path in files[keep:]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed


def verify_backup(path: Path) -> tuple[bool, str]:
    """Проверить, что снимок открывается и целостен."""
    try:
        if path.suffix == ".gz":
            tmp = path.with_suffix("")  # matches_....db
            with gzip.open(path, "rb") as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            try:
                return check_db_integrity(tmp)
            finally:
                tmp.unlink(missing_ok=True)
        return check_db_integrity(path)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------- git
def _git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def git_is_repo() -> bool:
    return _git("rev-parse", "--is-inside-work-tree").returncode == 0


def git_status_short() -> list[str]:
    out = _git("status", "--porcelain").stdout or ""
    return [line for line in out.splitlines() if line.strip()]


def git_commit(message: str, *, add_all: bool = True) -> tuple[bool, str]:
    """Закоммитить изменения. Возвращает (успех, текст)."""
    if not git_is_repo():
        return False, "не git-репозиторий"
    if add_all:
        add = _git("add", "-A")
        if add.returncode != 0:
            return False, f"git add: {add.stderr.strip()}"
    commit = _git("commit", "-m", message)
    if commit.returncode != 0:
        text = (commit.stdout + commit.stderr).strip()
        if "nothing to commit" in text or "нечего коммитить" in text:
            return True, "изменений нет — коммит не нужен"
        return False, f"git commit: {text}"
    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    return True, f"коммит {head} создан"


def git_tag(name: str, message: str) -> tuple[bool, str]:
    res = _git("tag", "-a", name, "-m", message)
    if res.returncode != 0:
        return False, res.stderr.strip()
    return True, f"тег {name} создан"


# --------------------------------------------------------------------- CLI
def main() -> int:
    parser = argparse.ArgumentParser(description="Ручной бэкап кода (git) и БД")
    parser.add_argument("--db-only", action="store_true", help="Только копия БД")
    parser.add_argument("--git-only", action="store_true", help="Только git-коммит")
    parser.add_argument("-m", "--message", default="", help="Сообщение коммита")
    parser.add_argument("--keep", type=int, default=20, help="Сколько копий БД хранить")
    parser.add_argument("--no-compress", action="store_true", help="Не сжимать копию БД")
    parser.add_argument("--tag", action="store_true", help="Поставить git-тег backup-*")
    parser.add_argument("--db", default="", help="Путь к БД (по умолчанию matches.db)")
    args = parser.parse_args()

    do_db = not args.git_only
    do_git = not args.db_only
    db_path = Path(args.db) if args.db else DB_PATH
    started = _stamp()
    problems: list[str] = []

    print("=" * 60)
    print("  Бэкап DeluX")
    print("=" * 60)

    # --- 1. Проверка БД
    if do_db:
        print(f"\n[1/3] Проверка БД: {db_path}")
        if not db_path.is_file():
            print(f"  [!] файл не найден: {db_path}")
            problems.append("БД не найдена")
            do_db = False
        else:
            print(f"  размер: {_fmt_mb(db_path.stat().st_size)}")
            ok, detail = check_db_integrity(db_path)
            if ok:
                print("  целостность: ok")
            else:
                print(f"  [!] целостность: {detail}")
                problems.append(f"БД повреждена: {detail}")

    # --- 2. Копия БД
    if do_db and not problems:
        print(f"\n[2/3] Снимок БД → {BACKUP_DIR.relative_to(ROOT)}")
        try:
            backup = make_db_backup(db_path, BACKUP_DIR, compress=not args.no_compress)
            print(f"  создан: {backup.name} ({_fmt_mb(backup.stat().st_size)})")
            ok, detail = verify_backup(backup)
            if ok:
                print("  проверка снимка: ok")
            else:
                print(f"  [!] снимок не прошёл проверку: {detail}")
                problems.append(f"снимок повреждён: {detail}")
            removed = prune_backups(BACKUP_DIR, args.keep)
            if removed:
                print(f"  удалено старых копий: {len(removed)}")
            total = sorted(BACKUP_DIR.glob("matches_*.db*"))
            print(f"  всего копий: {len(total)} (храню {args.keep})")
        except Exception as exc:  # noqa: BLE001
            print(f"  [!] ошибка снимка: {exc}")
            problems.append(f"снимок не создан: {exc}")

    # --- 3. Git
    if do_git:
        print("\n[3/3] Git")
        if not git_is_repo():
            print("  [!] не git-репозиторий")
            problems.append("нет git-репозитория")
        else:
            changes = git_status_short()
            print(f"  изменённых файлов: {len(changes)}")
            if not changes:
                print("  изменений нет — коммитить нечего")
            else:
                for line in changes[:10]:
                    print(f"    {line}")
                if len(changes) > 10:
                    print(f"    … и ещё {len(changes) - 10}")

                message = args.message.strip()
                if not message:
                    if sys.stdin.isatty():
                        default = f"backup: {started}"
                        try:
                            message = input(f"  Сообщение коммита [{default}]: ").strip()
                        except (EOFError, KeyboardInterrupt, OSError):
                            message = ""
                        message = message or default
                    else:
                        message = f"backup: {started}"
                ok, detail = git_commit(message)
                print(f"  {detail}")
                if not ok:
                    problems.append(detail)
                elif args.tag:
                    tag_name = f"backup-{started[:8]}-{started[9:13]}{started[13:15]}"
                    ok_tag, detail_tag = git_tag(tag_name, message)
                    print(f"  {detail_tag}")
                    if not ok_tag:
                        problems.append(detail_tag)

    # --- Итог
    print("\n" + "=" * 60)
    if problems:
        print("  [!] ЕСТЬ ПРОБЛЕМЫ:")
        for p in problems:
            print(f"      - {p}")
        print("=" * 60)
        return 1
    print("  [+] Бэкап завершён успешно")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
