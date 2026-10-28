"""Проверка fetch_team_matches_before: глубокая пагинация до старой даты."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from team_history import fetch_team_matches_before, format_match_date  # noqa: E402

# Матч WzuV5eoq: Манчестер Юнайтед (ppjDR086) 1:0 Тоттенхэм (UDg08Ohm), 2015.08.08
TARGET_TS = 1439034300  # 2015.08.08 14:45 UTC
COUNTRY = 198
SPORT = 1


def main() -> int:
    print(f"целевой момент: {format_match_date(TARGET_TS)}\n")
    for key, name in (("ppjDR086", "Манчестер Юнайтед"), ("UDg08Ohm", "Тоттенхэм")):
        matches = fetch_team_matches_before(
            key, TARGET_TS, country=COUNTRY, sport=SPORT, limit=40, max_pages=20
        )
        print(f"{name} ({key}): {len(matches)} матчей ДО целевого")
        if matches:
            print(f"  от {format_match_date(matches[0]['kickoff_ts'])} "
                  f"до {format_match_date(matches[-1]['kickoff_ts'])}")
            print(f"  последний (ближайший к цели): "
                  f"{matches[-1]['home_name']} {matches[-1]['home_score']}:{matches[-1]['away_score']} "
                  f"{matches[-1]['away_name']} @ {format_match_date(matches[-1]['kickoff_ts'])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
