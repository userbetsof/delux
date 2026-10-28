"""Пересобрать team_form_stats для команд (дата + турнир в «последних матчах»).

Нужно после починки дат в matches: stats_json хранит уже посчитанный список
матчей, поэтому пустые даты остаются в кэше, пока не пересчитать.

    py -3 scripts/rebuild_form_stats.py --dry-run
    py -3 scripts/rebuild_form_stats.py --team "Расинг"
    py -3 scripts/rebuild_form_stats.py            # все команды из team_form_stats
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path  # noqa: E402
from team_stats_5matches import (  # noqa: E402
    analyze_team_form,
    save_team_stats_to_db,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--team", default="")
    args = parser.parse_args()

    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    try:
        if args.team:
            teams = [args.team]
        else:
            teams = [
                r["team_name"]
                for r in conn.execute(
                    "SELECT team_name FROM team_form_stats ORDER BY team_name"
                )
            ]
    finally:
        conn.close()

    print(f"команд: {len(teams)}")
    ok = fail = 0
    for i, team in enumerate(teams, 1):
        try:
            analysis = analyze_team_form(team)
            if not analysis:
                print(f"[{i}/{len(teams)}] {team}: нет данных")
                continue
            matches = analysis.get("matches") or []
            dated = sum(1 for m in matches if (m.get("date") or "").strip())
            toured = sum(1 for m in matches if (m.get("tournament") or "").strip())
            if not args.dry_run:
                save_team_stats_to_db(team, analysis)
            ok += 1
            if args.team or i <= 3:
                print(
                    f"[{i}/{len(teams)}] {team}: матчей {len(matches)}, "
                    f"с датой {dated}, с турниром {toured}"
                )
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(teams)}] {team}: FAIL {type(exc).__name__}: {exc}")

    print(f"\nготово: пересобрано {ok}, ошибок {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
