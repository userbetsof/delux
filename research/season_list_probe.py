"""Найти season_list на странице лиги и получить name по stage (faBBhyuM)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))


def fetch_page(url: str) -> str:
    import urllib.request
    from flashscore_feed import API_HEADERS
    req = urllib.request.Request(url, headers=dict(API_HEADERS))
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def parse_season_list(html: str):
    """Извлечь season_list — массив {id, name, pathname}."""
    # ищем массив объектов с pathname /standings/...
    m = re.search(r'(\[\{"id":\d+,"name":"[^"]*","pathname":"/standings/.*?\}\])', html)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return []


def main() -> int:
    for slug in ("premier-league",):
        url = f"https://www.flashscore.com/football/england/{slug}/results/"
        try:
            html = fetch_page(url)
        except Exception as e:  # noqa: BLE001
            print(f"{slug}: ERROR {type(e).__name__} {e}")
            continue
        print(f"{slug}: len={len(html)}")
        seasons = parse_season_list(html)
        print(f"season_list: {len(seasons)} сезонов")
        for s in seasons:
            print("  ", s)
        # ищем сезон со stage faBBhyuM
        for s in seasons:
            if "faBBhyuM" in s.get("pathname", ""):
                print(f"\nЦЕЛЕВОЙ СЕЗОН (stage faBBhyuM): {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
