"""Полный пайплайн DeluX: загрузка матчей → проверка результатов → анализ новых."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parents[2]
os.chdir(SCRIPT_DIR)


def run_pipeline(
    workbook: str = "",
    auto: bool | None = None,
    limit: int = 0,
    *,
    db_only: bool = True,
) -> int:
    from settings import DeluxSettings

    py = sys.executable
    if auto is None:
        auto = DeluxSettings.from_env().list_auto_default()

    print("[1/3] Загрузка списка матчей...")
    cmd_list = [py, "-X", "utf8", str(SCRIPT_DIR / "matches_list.py")]
    if auto:
        cmd_list.append("--auto")
    elif auto is False:
        cmd_list.append("--no-auto")
    if not db_only:
        cmd_list.extend(["--excel", "--workbook", workbook or ""])
    r1 = subprocess.run(cmd_list, cwd=str(SCRIPT_DIR))
    if r1.returncode != 0:
        print(f"[-] matches_list завершился с кодом {r1.returncode}")
        return r1.returncode
    print("[+] Список загружен в БД")

    print("\n[2/3] Проверка результатов матчей...")
    try:
        from result_checker import run_db_check

        rc = run_db_check()
        if rc != 0:
            print(f"[!] check завершился с кодом {rc}, продолжаем анализ")
    except Exception as exc:
        print(f"[!] check не удался: {exc}, продолжаем анализ")

    print("\n[3/3] Анализ новых матчей...")
    if limit > 0:
        os.environ["ANALYZE_LIMIT"] = str(limit)
    cmd_an = [py, "-X", "utf8", str(SCRIPT_DIR / "analyze_match.py"), "--new"]
    if workbook:
        cmd_an.extend(["--workbook", workbook])
    r2 = subprocess.run(cmd_an, cwd=str(SCRIPT_DIR))
    return r2.returncode


def main():
    parser = argparse.ArgumentParser(description="DeluX: matches_list + analyze_match --new")
    parser.add_argument("--workbook", default="")
    parser.add_argument(
        "--auto",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Все виды из DELUX_SPORTS_AUTO (по умолчанию: да, если их >1)",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--excel", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        run_pipeline(
            workbook=args.workbook,
            auto=args.auto,
            limit=args.limit,
            db_only=not args.excel,
        )
    )


if __name__ == "__main__":
    main()
