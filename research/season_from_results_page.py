"""Достать season_id + tournament_key из страницы результатов лиги.

На странице вроде /football/england/premier-league-2015-2016/results/
есть `cjs.initialFeeds['results'] = { data: ZH÷198_dYlOSQOD, allEventsCount, seasonId }`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))


def fetch_page(url: str) -> str:
    import urllib.request
    from flashscore_feed import API_HEADERS
    req = urllib.request.Request(
        url,
        headers={**dict(API_HEADERS), "Referer": url.split("/x/")[0] + "/"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def parse_initial_feed(html: str) -> dict:
    """Извлечь cjs.initialFeeds['results'] из HTML."""
    m = re.search(r"cjs\.initialFeeds\[['\"]results['\"]\]\s*=\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", html)
    if not m:
        return {}
    body = m.group(0)
    out: dict = {}
    if mo := re.search(r"allEventsCount:\s*(\d+)", body):
        out["allEventsCount"] = int(mo.group(1))
    if mo := re.search(r"seasonId:\s*(\d+)", body):
        out["seasonId"] = mo.group(1)
    if mo := re.search(r"data:\s*`([^`]*)`", body):
        out["data"] = mo.group(1)
    return out


def main() -> int:
    urls = [
        "https://www.flashscorekz.com/football/england/premier-league-2015-2016/results/",
        "https://www.flashscore.com/football/england/premier-league-2015-2016/results/",
    ]
    for url in urls:
        try:
            html = fetch_page(url)
        except Exception as e:  # noqa: BLE001
            print(f"{url}: ERROR {type(e).__name__} {e}")
            continue
        print(f"{url}: len={len(html)}")
        parsed = parse_initial_feed(html)
        print("  parsed:", parsed)
        # data = ZH÷198_dYlOSQOD → извлекаем tournament_key
        data = parsed.get("data", "")
        m = re.search(r"ZH÷(\w+)", data)
        print("  ZH (198_...):", m.group(1) if m else None)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
