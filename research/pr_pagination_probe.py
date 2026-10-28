"""Проверка глубины пагинации pr_ фида: диапазон дат по страницам."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from team_history import pr_feed_url, parse_pr_feed, format_match_date  # noqa: E402
from flashscore_feed import fetch_feed  # noqa: E402

TEAM = "hA1Zm19f"  # Арсенал
COUNTRY = 198
SPORT = 1


def main() -> int:
    for page in range(0, 12):
        url = pr_feed_url(SPORT, COUNTRY, TEAM, page)
        try:
            text = fetch_feed(url, retries=2, timeout=40)
        except Exception as exc:  # noqa: BLE001
            print(f"page {page}: ERROR {exc}")
            continue
        matches = parse_pr_feed(text)
        if not matches:
            print(f"page {page}: пусто (конец истории)")
            break
        ts = [m["kickoff_ts"] for m in matches if m["kickoff_ts"]]
        print(f"page {page}: {len(matches)} матчей, "
              f"{format_match_date(min(ts))} .. {format_match_date(max(ts))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
