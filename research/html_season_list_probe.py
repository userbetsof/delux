"""Найти соответствие (stage -> числовой seasonId) из JSON сезонов страницы турнира."""
from __future__ import annotations

import json
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

    # найдём JSON массив сезонов (там где pathname /standings/...)
    m = re.search(r'\[(\{"id":\d+,"name":"[^"]*","pathname":"/standings/.*?\})\]', html)
    if m:
        arr = json.loads(m.group(1))
        print("сезоны (id, name, pathname):")
        for s in arr:
            print(f"  id={s['id']} name={s['name']} pathname={s['pathname']}")
    else:
        print("не найден массив сезонов")

    # ищем все seasonId с контекстом
    print("\n=== seasonId контекст ===")
    for mm in re.finditer(r'seasonId["\']?\s*[:=]\s*("?\d+"?)', html):
        s = mm.start()
        print(html[max(0, s - 80): s + 80].replace("\n", " "))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
