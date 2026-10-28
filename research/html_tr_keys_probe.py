"""Найти в HTML страницы матча все id, нужные для tr_ URL (ZEE + season)."""
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

    print("len =", len(html))

    needle = ("dYlOSQOD", "faBBhyuM", "OhnzLqf7", "165")
    for n in needle:
        idx = html.find(n)
        print(f"{n!r}: index={idx}")
        if idx >= 0:
            print("   контекст:", html[max(0, idx - 120): idx + 120].replace("\n", " "))

    # ищем поля, где рядом стоят dYlOSQOD и 165
    print("\n--- паттерны вокруг dYlOSQOD ---")
    for m in re.finditer(r"dYlOSQOD", html):
        s = m.start()
        print(html[max(0, s - 200): s + 200].replace("\n", " "))
        print("===")
        break  # только первое вхождение

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
