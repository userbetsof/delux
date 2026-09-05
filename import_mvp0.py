"""
Перенос из DeluX_IncoProrok_mvp0.xlsm → matches.db + сигналы 1pr.

Использование (после расчёта матча в Excel mvp0 и сохранения книги):
  py import_mvp0.py              # текущий матч (архив + Анализ + кэфы) → БД + 1pr
  py import_mvp0.py --dry-run    # только показать, что будет записано
  py import_mvp0.py --workbook PATH
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from db import (  # noqa: E402
    DEBUG_MODE,
    create_database,
    insert_match_data_with_probabilities,
    read_excel_file,
    resolve_workbook_path,
    close_all_connections,
)
from telegram_client import TelegramNotifier  # noqa: E402


def _print_preview(data: dict) -> None:
    odds = data.get("odds_data") or {}
    markets = odds.get("markets") or []
    print(f"  match_id : {data.get('id') or data.get('match_id')}")
    print(f"  sport    : {data.get('sport')}")
    print(f"  date     : {data.get('match_date')}")
    print(f"  league   : {data.get('league')}")
    print(f"  teams    : {data.get('home')} - {data.get('away')}")
    print(f"  pred NTB : {data.get('prediction')}")
    print(f"  odds mkts: {len(markets)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Импорт текущего матча из mvp0.xlsm в matches.db и 1pr"
    )
    parser.add_argument(
        "--workbook",
        default="",
        help="Путь к .xlsm (по умолчанию DeluX_IncoProrok_mvp0.xlsm из .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только прочитать Excel, без записи в БД",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Не слать Telegram",
    )
    args = parser.parse_args()

    try:
        wb_path = resolve_workbook_path(args.workbook or None)
    except FileNotFoundError as exc:
        print(f"[-] {exc}")
        return 1

    print(f"[*] Excel: {wb_path}")
    if "mvp0" not in os.path.basename(wb_path).lower():
        print("[!] Внимание: книга не mvp0 — проверьте .env / --workbook")

    create_database()
    data = read_excel_file(wb_path)
    if not data:
        print("[-] Не удалось прочитать данные из Excel (achive / Анализ / кэфы)")
        return 1

    print("[*] Данные из Excel:")
    _print_preview(data)

    if args.dry_run or DEBUG_MODE:
        print("[*] dry-run / DEBUG_MODE — запись пропущена")
        return 0

    ok = insert_match_data_with_probabilities(data, wb_path)
    if not ok:
        print("[-] Ошибка записи в matches.db")
        return 1

    mid = str(data.get("id") or data.get("match_id") or "")
    print(f"[+] matches.db: матч {mid} сохранён (вероятности + кэфы)")
    print("[*] 1pr: хук вызывается из insert_outcome_probabilities_from_analysis")

    if not args.no_telegram:
        telegram = TelegramNotifier()
        if telegram.is_configured:
            text = (
                f"[+] Прогноз (mvp0):\n"
                f"Дата: {data.get('match_date', 'N/D')}\n"
                f"Турнир: {data.get('league', 'N/D')}\n"
                f"Команды: {data.get('home', 'N/D')} - {data.get('away', 'N/D')}\n"
                f"Прогноз: {data.get('prediction', 'N/D')}"
            )
            if telegram.send(text):
                print("[+] Telegram отправлен")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        close_all_connections()
