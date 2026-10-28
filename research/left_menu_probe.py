"""Найти ссылку лиги в left_menu_categories_seo и понять, как строится URL сезона."""
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
    html = fetch_page("https://www.flashscore.com/match/WzuV5eoq/")
    print("len =", len(html))

    # блок left_menu_categories_seo
    idx = html.find("left_menu_categories_seo")
    print("left_menu_categories_seo idx:", idx)
    if idx >= 0:
        seg = html[idx: idx + 3000]
        print(seg[:2000])

    print("\n=== все href в этом блоке ===")
    seg = html[idx: idx + 8000] if idx >= 0 else ""
    for m in re.finditer(r'href="([^"]+)"', seg):
        print("  ", m.group(1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
