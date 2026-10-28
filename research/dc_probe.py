"""Разведка dc_ фида для матча WzuV5eoq (детали матча)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from flashscore_feed import fetch_feed, parse_fields, iter_feed_rows  # noqa: E402

MATCH_ID = "WzuV5eoq"


def dump(sport: int) -> None:
    for host in ("www.flashscorekz.com", "46.flashscore.ninja"):
        url = f"https://{host}/x/feed/dc_{sport}_{MATCH_ID}"
        try:
            text = fetch_feed(url, retries=2, timeout=20)
        except Exception as exc:  # noqa: BLE001
            print(f"[sport={sport} host={host}] ERROR: {exc}")
            continue
        print(f"[sport={sport} host={host}] len={len(text)}")
        print(text[:1500])
        print()
        return
    print(f"[sport={sport}] не удалось получить")


def main() -> int:
    for sport in (1, 4, 6):
        dump(sport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
