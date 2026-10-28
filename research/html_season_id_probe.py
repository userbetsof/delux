"""Получить числовой seasonId для конкретного сезона через /standings/{t}/{s}/."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))


def _get(url):
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main() -> int:
    # сезон 2015/16 = /standings/OhnzLqf7/faBBhyuM/
    url = "https://www.flashscore.com/standings/OhnzLqf7/faBBhyuM/"
    try:
        html = _get(url)
    except Exception as e:
        print("ERROR:", type(e).__name__, e)
        return 1

    print("len =", len(html))
    for m in re.finditer(r"seasonId[^,}]{0,30}", html):
        print("  ", m.group(0))
    # ищем seasonId: N
    ids = re.findall(r"seasonId[:\s]*(\d+)", html)
    print("seasonId значения:", ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
