"""Отладить извлечение league_link из HTML матча."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from tournament_resolver import _fetch, _match_page_data  # noqa: E402


def main() -> int:
    html = _fetch("https://www.flashscore.com/match/WzuV5eoq/")
    d = _match_page_data("WzuV5eoq")
    print("match_page_data:", d)

    # ищем "link" рядом с tournament
    print("\n=== все 'link' рядом с 'football/england' ===")
    for m in re.finditer(r'"link":"(\\?/[^"]+)"', html):
        s = m.group(1)
        if "premier-league" in s or "england" in s:
            print("  ", s)

    # контекст tournament.link
    i = html.find('"tournament":{"')
    if i >= 0:
        print("\n=== контекст tournament.link ===")
        print(html[i: i + 400].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
