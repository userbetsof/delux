"""Найти season id (числовой) в HTML через ссылки турнира/архива."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))


def main() -> int:
    import urllib.request

    url = "https://www.flashscore.com/match/WzuV5eoq/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")

    # ссылки турнира с параметрами
    print("=== ссылки на premier-league ===")
    for m in re.finditer(r'/football/england/premier-league/[^"\']*', html):
        print("  ", m.group(0))
    print()

    # ищем url вида .../archive/ или со seasonId
    print("=== archive/season ссылки ===")
    seen = set()
    for m in re.finditer(r'[^"\']*(?:archive|season|stage)[^"\']*', html):
        s = m.group(0)
        if len(s) < 100 and s not in seen:
            seen.add(s)
            print("  ", s)
    print()

    # pageinfo целиком
    m = re.search(r'pageinfo\s*=\s*(\{.*?\});', html)
    if m:
        print("=== pageinfo ===")
        print(m.group(1))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
