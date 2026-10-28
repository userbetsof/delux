"""Найти season_list / массив сезонов в сыром виде на странице лиги."""
from __future__ import annotations

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


def main() -> int:
    url = "https://www.flashscore.com/football/england/premier-league/results/"
    html = fetch_page(url)
    print("len =", len(html))

    # где встречается faBBhyuM / OhnzLqf7 / season_list / 2015
    for needle in ("faBBhyuM", "OhnzLqf7", "season_list", "2015/2016", "season"):
        idx = html.find(needle)
        print(f"{needle!r}: idx={idx}")

    print("\n=== контекст faBBhyuM ===")
    i = html.find("faBBhyuM")
    if i >= 0:
        seg = html[i - 400: i + 300].replace("\n", " ")
        print(seg)

    print("\n=== контекст season_list ===")
    i = html.find("season_list")
    if i >= 0:
        print(html[i - 100: i + 400].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
