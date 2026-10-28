"""Найти числовой season id в HTML (нужен для tr_ URL)."""
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

    # season-related ключи
    for pat in (
        r'"season[A-Za-z]*"\s*:\s*"?([\w\-]+)"?',
        r'"season[A-Za-z]*"[:=]\s*"?([\w\-]+)"?',
        r'seasonId["\']?\s*[:=]\s*["\']?([\d]+)',
    ):
        found = re.findall(pat, html)
        print(f"{pat}: {found[:10]}")

    # ищем '165' рядом с dYlOSQOD / season
    print("\nконтекст 'season':")
    for m in re.finditer(r"season", html):
        s = m.start()
        seg = html[s - 40: s + 60].replace("\n", " ")
        if re.search(r"\d{2,3}", seg):
            print("  ", seg)

    # страница может хранить __NEXT_DATA__ JSON
    nd = html.find("__NEXT_DATA__")
    print("\n__NEXT_DATA__ at:", nd)

    # ищем tournamentTemplateId + seasonId вместе
    keys = re.findall(r'tournamentTemplateId["\']?\s*[:=]\s*["\']?([\w\-]+)["\']?', html)
    print("tournamentTemplateId:", keys)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
