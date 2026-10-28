"""Найти точный вид cjs.initialFeeds['results'] в HTML."""
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
    url = "https://www.flashscore.com/football/england/premier-league-2015-2016/results/"
    html = fetch_page(url)
    print("len =", len(html))

    for needle in ("results", "initialFeeds", "seasonId", "allEventsCount", "ZH÷"):
        idx = html.find(needle)
        print(f"{needle!r}: idx={idx}")

    # все вхождения initialFeeds и seasonId
    print("\n=== initialFeeds ===")
    for m in re.finditer(r"initialFeeds", html):
        s = m.start()
        print(html[s - 40: s + 120].replace("\n", " "))
        print("---")

    print("\n=== seasonId ===")
    for m in re.finditer(r"seasonId", html):
        s = m.start()
        print(html[s - 60: s + 80].replace("\n", " "))
        print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
