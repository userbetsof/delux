"""Загрузка снимка БД в Google Drive.

Поддерживаются три способа (по убыванию предпочтения):

1. rclone — если установлен и настроен remote (например `gdrive`).
   Команда: rclone copy <файл> gdrive:DeluX/backups/db/
   Настройка один раз: `rclone config` → новый remote → Google Drive.

2. Папка локальной синхронизации — Google Drive для ПК.
   Если задан DELUX_GDRIVE_DIR (или найден стандартный путь), файл просто
   копируется туда, а клиент сам отправляет его в облако.

3. Пропуск — ничего не настроено, пишем об этом и не считаем ошибкой.

Настройка через переменные окружения:
    DELUX_GDRIVE_REMOTE   имя rclone-remote (по умолчанию gdrive)
    DELUX_GDRIVE_PATH     путь внутри remote (по умолчанию DeluX/backups/db)
    DELUX_GDRIVE_DIR      путь к локальной папке Google Drive
    DELUX_NO_GDRIVE=1     отключить загрузку
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def gdrive_disabled() -> bool:
    value = _env("DELUX_NO_GDRIVE").lower()
    return value in ("1", "true", "yes", "on")


# Имена, которые считаем «нашим» Google Drive, если явно не задан
# DELUX_GDRIVE_REMOTE. Порядок = приоритет.
_PREFERRED_REMOTES = ("gdrive", "delux", "google", "gdrive-delux")


def default_remote() -> str:
    return _env("DELUX_GDRIVE_REMOTE") or ""


def default_remote_path() -> str:
    return _env("DELUX_GDRIVE_PATH", "DeluX/backups/db") or "DeluX/backups/db"


def pick_remote(remotes: list[str]) -> str:
    """Выбрать remote для загрузки.

    1. DELUX_GDRIVE_REMOTE, если задан и существует.
    2. Первое совпадение из _PREFERRED_REMOTES.
    3. Если настроен ровно один remote — используем его (имя не важно:
       пользователь мог назвать его как угодно, например 'delux').
    """
    explicit = default_remote()
    if explicit:
        return explicit
    lower = {r.lower(): r for r in remotes}
    for name in _PREFERRED_REMOTES:
        if name in lower:
            return lower[name]
    if len(remotes) == 1:
        return remotes[0]
    return "gdrive"


def remote_type(exe: str, name: str) -> str:
    """Тип remote (drive / onedrive / …) — чтобы предупредить, если это не Drive."""
    try:
        res = subprocess.run(
            [exe, "config", "show", name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except Exception:  # noqa: BLE001
        return ""
    for line in (res.stdout or "").splitlines():
        if line.strip().lower().startswith("type"):
            _, _, value = line.partition("=")
            return value.strip()
    return ""


def find_rclone() -> Optional[str]:
    """Путь к rclone.exe, если он доступен."""
    exe = shutil.which("rclone")
    if exe:
        return exe
    for candidate in (
        Path(r"C:\Program Files\rclone\rclone.exe"),
        Path(r"C:\Program Files (x86)\rclone\rclone.exe"),
        Path.home() / "rclone" / "rclone.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def rclone_remotes(exe: str) -> list[str]:
    """Список настроенных remote'ов rclone."""
    try:
        res = subprocess.run(
            [exe, "listremotes"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except Exception:  # noqa: BLE001
        return []
    if res.returncode != 0:
        return []
    return [line.strip().rstrip(":") for line in (res.stdout or "").splitlines() if line.strip()]


def gdrive_local_dir() -> Optional[Path]:
    """Папка Google Drive для ПК (если клиент установлен)."""
    explicit = _env("DELUX_GDRIVE_DIR")
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    user = Path.home()
    candidates += [
        user / "Google Drive" / "My Drive" / "DeluX",
        user / "Google Drive" / "Мой диск" / "DeluX",
        user / "GoogleDrive" / "My Drive" / "DeluX",
    ]
    for path in candidates:
        parent = path if path.name != "DeluX" else path.parent
        if parent.is_dir():
            return path
    return None


def status() -> dict:
    """Что настроено — для вывода в консоль."""
    exe = find_rclone()
    remotes = rclone_remotes(exe) if exe else []
    remote = pick_remote(remotes)
    rtype = remote_type(exe, remote) if (exe and remote in remotes) else ""
    local = gdrive_local_dir()
    return {
        "disabled": gdrive_disabled(),
        "rclone": exe or "",
        "remotes": remotes,
        "remote": remote,
        "remote_ready": bool(exe) and remote in remotes,
        "remote_type": rtype,
        "remote_path": default_remote_path(),
        "local_dir": str(local) if local else "",
    }


def upload(backup_path: Path, *, dry_run: bool = False) -> tuple[bool, str]:
    """Отправить файл в Google Drive. Возвращает (успех, текст).

    Успех также при «нечего отправлять» (наружу ничего не уходит) —
    чтобы бэкап не считался проваленным только из-за ненастроенного облака.
    """
    if gdrive_disabled():
        return True, "Google Drive отключён (DELUX_NO_GDRIVE=1)"
    if not backup_path.is_file():
        return False, f"файл не найден: {backup_path}"

    exe = find_rclone()
    remotes = rclone_remotes(exe) if exe else []
    remote = pick_remote(remotes)
    if exe and remote in remotes:
        target = f"{remote}:{default_remote_path()}"
        cmd = [exe, "copy", str(backup_path), target, "--stats-one-line", "--stats=0"]
        if dry_run:
            return True, f"[dry-run] rclone copy → {target}"
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1800,
            )
        except subprocess.TimeoutExpired:
            return False, "rclone: таймаут"
        except Exception as exc:  # noqa: BLE001
            return False, f"rclone: {exc}"
        if res.returncode == 0:
            return True, f"загружено в {target}"
        err = (res.stderr or res.stdout or "").strip().splitlines()
        return False, f"rclone: {' '.join(err[:3])}"

    local = gdrive_local_dir()
    if local is not None:
        if dry_run:
            return True, f"[dry-run] копия в {local}"
        try:
            local.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, local / backup_path.name)
            return True, f"скопировано в {local}"
        except Exception as exc:  # noqa: BLE001
            return False, f"копия в Google Drive: {exc}"

    if exe:
        return True, (
            f"rclone найден, но remote '{remote}' не настроен — "
            f"выполните: rclone config"
        )
    return True, (
        "не настроено: установите rclone (winget install Rclone.Rclone) "
        "и создайте remote 'gdrive', либо задайте DELUX_GDRIVE_DIR"
    )


def main() -> int:
    """CLI: показать состояние или загрузить конкретный файл."""
    import argparse

    parser = argparse.ArgumentParser(description="Загрузка бэкапа в Google Drive")
    parser.add_argument("--status", action="store_true", help="Показать настройку")
    parser.add_argument("--file", default="", help="Файл для загрузки")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status or not args.file:
        st = status()
        print("Google Drive:")
        print(f"  отключён:        {st['disabled']}")
        print(f"  rclone:          {st['rclone'] or 'не найден'}")
        print(f"  remote'ы:        {', '.join(st['remotes']) or '—'}")
        ready = "настроен" if st["remote_ready"] else "НЕ настроен"
        print(f"  используем:      {st['remote']} ({ready})")
        if st.get("remote_type"):
            mark = "" if st["remote_type"] == "drive" else "  [!] это не Google Drive"
            print(f"  тип:             {st['remote_type']}{mark}")
        print(f"  путь в облаке:   {st['remote_path']}")
        print(f"  локальная папка: {st['local_dir'] or '—'}")
        if not args.file:
            return 0

    ok, detail = upload(Path(args.file), dry_run=args.dry_run)
    print(f"  {'[+]' if ok else '[!]'} {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
