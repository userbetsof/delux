"""Разведка pr_ feed (последние матчи команды)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from flashscore_feed import fetch_feed, iter_feed_rows, parse_fields  # noqa: E402

URL = "https://46.flashscore.ninja/46/x/feed/pr_1_81_nP1i5US1_0_3_ru-kz_1"


def main() -> int:
    text = fetch_feed(URL)
    print("len =", len(text))
    print("--- первые 1200 символов ---")
    print(text[:1200])
    print()

    # парсим по строкам
    rows = list(iter_feed_rows(text))
    print(f"строк-записей: {len(rows)}")

    # какие ключи встречаются (первый элемент каждой записи)
    from collections import Counter
    keys = Counter(k for k, _, _ in rows)
    print("ключи:", sorted(keys.items()))

    # смотрим записи, которые являются матчами (ключ AA — начало матча)
    matches = []
    current = {}
    for k, v, fields in rows:
        if k == "AA":
            if current:
                matches.append(current)
            current = {}
        parsed = parse_fields(fields)
        current.update(parsed)
    if current:
        matches.append(current)

    print(f"\nматчей (по AA): {len(matches)}")
    if matches:
        print("\n--- ПОЛНАЯ СТРУКТУРА ПЕРВОГО МАТЧА ---")
        for k, v in matches[0].items():
            print(f"  {k} = {v!r}")
        print("\n--- ВТОРОЙ ---")
        for k, v in matches[1].items():
            print(f"  {k} = {v!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
