"""Найти season id из страницы турнира (списка сезонов)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))


def main() -> int:
    import urllib.request

    url = "https://www.flashscore.com/football/england/premier-league/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")

    print("len =", len(html))

    # ищем season id рядом с dYlOSQOD или faBBhyuM
    for token in ("dYlOSQOD", "faBBhyuM", "OhnzLqf7"):
        for m in re.finditer(token, html):
            s = m.start()
            seg = html[max(0, s - 250): s + 250].replace("\n", " ")
            print(f"\n=== {token} @ {s} ===")
            print(seg)
            break  # первое вхождение

    # ищем блок со season и числами
    print("\n=== season id кандидаты ===")
    for m in re.finditer(r'season[A-Za-z]*["\']?\s*[:=]\s*["\']?(\d{2,6})', html):
        print("  ", m.group(0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
