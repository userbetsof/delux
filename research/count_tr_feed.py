"""Считает реальное число матчей в tr_ фиде по всем страницам."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from test_flashscore import fetch_feed, parse_tr_feed  # noqa: E402

BASE = "https://46.flashscore.ninja/46/x/feed/tr_1_198_dYlOSQOD_165_{page}_1_ru-kz_1"


def main() -> int:
    seen: dict[str, str] = {}
    for page in range(0, 10):
        url = BASE.format(page=page)
        text = fetch_feed(url)
        if not text or len(text) < 100:
            print(f"page {page}: EMPTY ({len(text)} bytes)")
            # не останавливаемся — проверяем, вдруг дальше есть
            continue
        matches = parse_tr_feed(text)
        ids = [m.get("AA", "") for m in matches]
        print(f"page {page}: {len(matches)} matches, len={len(text)}")
        for m in matches:
            seen.setdefault(m.get("AA", ""), m.get("ER", ""))
        if page > 4:
            print(f"  (проверяю доп. страницы)")
    print(f"\nВСЕГО уникальных match_id: {len(seen)}")
    # распределение по турам
    from collections import Counter
    rounds = Counter(v for v in seen.values())
    print(f"по турам: {sorted(rounds.items())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
