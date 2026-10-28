"""Разведка: какие id турнира/сезона есть на HTML-странице матча."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))

from analysis_data import fetch_match_page_html, fetch_match_page_ids  # noqa: E402


def main() -> int:
    html = fetch_match_page_html("WzuV5eoq")
    print("HTML len:", len(html))

    # ищем известные токены
    for token in (
        "tournamentEncodedId",
        "seasonEncodedId",
        "tournamentStage",
        "tournament",
        "season",
        "dYlOSQOD",
        "165",
        "stageId",
    ):
        found = html.find(token)
        print(f"{token!r}: {found}")

    print("\nfetch_match_page_ids:", fetch_match_page_ids("WzuV5eoq"))

    # вытащим блоки JSON, содержащие id
    for m in re.finditer(r'"(tournament[A-Za-z]*|season[A-Za-z]*|stage[A-Za-z]*)"\s*:\s*"([\w-]+)"', html):
        print("JSON id:", m.group(1), "=", m.group(2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
