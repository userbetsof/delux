"""Пересчёт матчей, у которых NTB (#1) не сохранился из-за пустой Poisson-сетки.

    py -3 scripts\\refill_ntb.py --dry-run
    py -3 scripts\\refill_ntb.py --limit 10
    py -3 scripts\\refill_ntb.py            # все незавершённые
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit("\\", 2)[0])

from analysis_data import MatchInfo, build_settings  # noqa: E402
from db import get_database_path  # noqa: E402
from match_analysis import _fetch_match_status, analyze_match  # noqa: E402
from match_store import QueuedMatch  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def target_matches(include_finished: bool) -> list[tuple[str, int]]:
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT m.match_id, m.sport
        FROM matches m
        WHERE m.prediction IS NOT NULL
          AND TRIM(m.prediction) NOT IN ('', '-')
          AND (
            (SELECT prediction FROM strategy_predictions sp
              WHERE sp.match_id = m.match_id AND sp.strategy_id = 1) IS NULL
            OR TRIM((SELECT prediction FROM strategy_predictions sp
              WHERE sp.match_id = m.match_id AND sp.strategy_id = 1)) = ''
          )
    """
    if not include_finished:
        sql += " AND (m.match_status IN ('0','1','2') OR m.match_status IS NULL)"
    sql += " ORDER BY m.start_ts"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [(r["match_id"], int(r["sport"] or 1)) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-finished", action="store_true")
    args = parser.parse_args()

    targets = target_matches(args.include_finished)
    if args.limit:
        targets = targets[: args.limit]
    print(f"матчей без NTB: {len(targets)}")
    if args.dry_run:
        ids = [t[0] for t in targets]
        print("  ", ", ".join(ids[:30]), "..." if len(ids) > 30 else "")
        return 0

    cfg = DeluxSettings.from_env()
    ok = fail = 0
    for i, (match_id, sport) in enumerate(targets, 1):
        settings = build_settings(
            sport=sport,
            source=cfg.source,
            tz_base=cfg.tz_base,
            dayzone_base=cfg.dayzone_base,
            time_offset=cfg.time_offset,
        )
        match = MatchInfo(match_id=match_id)
        try:
            match.status = _fetch_match_status(match_id, sport)
            res = analyze_match(
                "",
                match,
                settings,
                save_to_db=True,
                queued=QueuedMatch(match_id=match_id, sport=sport),
                only_strategies={1, 2, 3},
            )
            ntb = res.get("prediction_ntb")
            print(f"[{i}/{len(targets)}] {match_id} (sport={sport}): NTB={ntb!r}")
            ok += 1 if ntb else 0
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(targets)}] {match_id}: FAIL {type(exc).__name__}: {exc}")
    print(f"\nготово: с NTB {ok}, ошибок {fail}, всего {len(targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
