"""Найти слаг лиги (premier-league) в HTML матча."""
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

    # ссылка на турнир (слаг) — около pageinfo или в breadcrumbs
    for needle in ("premier-league", "tournament", "breadcrumb", "detailSK"):
        i = html.find(needle)
        print(f"{needle!r}: idx={i}")

    # breadcrumbs / ссылка на лигу
    print("\n=== контекст 'premier-league' ===")
    for m in re.finditer(r"premier-league", html):
        s = m.start()
        print(html[max(0, s - 120): s + 120].replace("\n", " "))
        print("---")
        break

    # JSON с категорией/лигой рядом с tournamentTemplateId
    i = html.find("tournamentTemplateId")
    print("\n=== pageinfo полный ===")
    m = re.search(r'pageinfo\s*=\s*(\{.*?\});', html, re.S)
    print(m.group(1) if m else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
