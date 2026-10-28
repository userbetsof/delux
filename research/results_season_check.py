"""Проверить: URL /premier-league-2015-2016/results/ даёт seasonId=165.

Слаг лиги + сезон из даты матча → страница результатов → seasonId.
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
    req = urllib.request.Request(url, headers=dict(API_HEADERS))
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def extract_results_feed(html: str) -> dict:
    """Извлечь cjs.initialFeeds['results'] = { data, allEventsCount, seasonId }."""
    # блок: cjs.initialFeeds['results'] = { ... }
    m = re.search(r"cjs\.initialFeeds\['results'\]\s*=\s*\{(.*?)\}\s*cjs\.Api", html, re.S)
    if not m:
        m = re.search(r"cjs\.initialFeeds\['results'\]\s*=\s*\{(.*?)\};", html, re.S)
    if not m:
        return {}
    body = m.group(1)
    out = {}
    if mo := re.search(r"seasonId:\s*(\d+)", body):
        out["seasonId"] = mo.group(1)
    if mo := re.search(r"allEventsCount:\s*(\d+)", body):
        out["allEventsCount"] = int(mo.group(1))
    if mo := re.search(r"data:\s*`([^`]*)`", body):
        d = mo.group(1)
        zm = re.search(r"ZEE÷(\w+)", d)
        out["tournament_key"] = zm.group(1) if zm else None
    return out


def main() -> int:
    # сезон 2015-2016 → слаг premier-league-2015-2016
    base = "https://www.flashscore.com/football/england/"
    for slug in ("premier-league-2015-2016",):
        url = f"{base}{slug}/results/"
        try:
            html = fetch_page(url)
        except Exception as e:  # noqa: BLE001
            print(f"{slug}: ERROR {type(e).__name__} {e}")
            continue
        r = extract_results_feed(html)
        print(f"{slug}: seasonId={r.get('seasonId')} allEventsCount={r.get('allEventsCount')} tournament_key={r.get('tournament_key')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
