"""Починить страну у лиг, попавших в 'Unknown'.

Причина: db.parse_league возвращает ('Unknown', league) если в строке лиги
нет ": " — так бывает, когда расчёт не дал league (бывает у восстановленных
матчей). В итоге «Примера» и др. висят под страной Unknown, и в «последних
матчах» турнир отображается как "Unknown: Примера".

Страна определяется по фиду: берём приз_матч из лиги и смотрим KG (country id)
в df_hh, либо ZB в pr_/tr_ заголовке. Проще — по известному списку
лиг->стран, собранному из тех же лиг с корректной страной в БД.

    py -3 scripts/fix_unknown_country.py --dry-run
    py -3 scripts/fix_unknown_country.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402
from feed_ids import feed_url  # noqa: E402
from flashscore_feed import fetch_feed  # noqa: E402

UNKNOWN_ID = 11


def country_for_match(match_id: str, sport: int = 1) -> str:
    """Страна матча из df_hh-фида (поле KG у любой игры секции)."""
    try:
        text = fetch_feed(feed_url(f"df_hh_{sport}_{match_id}"), retries=1, timeout=20)
    except Exception:  # noqa: BLE001
        return ""
    for chunk in (text or "").split("¬~"):
        for field in chunk.split("¬"):
            key, sep, value = field.partition("÷")
            if sep and key == "KG" and value.strip():
                return value.strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        leagues = conn.execute(
            "SELECT id, name FROM leagues WHERE country_id = ?", (UNKNOWN_ID,)
        ).fetchall()
        print(f"лиг под Unknown: {len(leagues)}")

        moved = 0
        for league in leagues:
            row = conn.execute(
                "SELECT match_id, sport FROM matches WHERE league_id = ? "
                "ORDER BY start_ts DESC LIMIT 1",
                (league["id"],),
            ).fetchone()
            if not row:
                print(f"  [{league['name']}] нет матчей — пропуск")
                continue
            kg = country_for_match(row["match_id"], int(row["sport"] or 1))
            if not kg:
                print(f"  [{league['name']}] не удалось определить страну")
                continue
            # KG — это id страны Flashscore (например 198), но в таблице
            # countries свои id. Ищем страну по матчам других лиг с тем же названием.
            print(f"  [{league['name']}] Flashscore country id = {kg} (матч {row['match_id']})")
            moved += 1
    finally:
        conn.close()

    print(f"\nразобрано лиг: {moved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
