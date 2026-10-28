"""Найти в HTML матча ссылку на страницу результатов/турнира со слагом сезона."""
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

    # все ссылки, содержащие премьер-лигу / season в слаге
    seen = set()
    for m in re.finditer(r'(https?:)?//[^"\'\s]*?(?:premier-league|england)[^"\'\s]*', html):
        s = m.group(0)
        if s not in seen:
            seen.add(s)
            print("  ", s)

    # ищем слаги вида -20XX-20XX в HTML
    print("\n=== слаги сезонов ===")
    for m in re.finditer(r'[a-z0-9\-]+\-\d{4}\-\d{4}', html):
        print("  ", m.group(0))

    # pageinfo + любые urls рядом
    print("\n=== pageinfo ===")
    m = re.search(r'pageinfo\s*=\s*(\{.*?\});', html)
    print(m.group(1) if m else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
