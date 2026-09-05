"""Пересчёт 1pr (#8) для матчей из очереди / БД DeluX."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import create_database, get_db_connection  # noqa: E402
from match_store import list_queued_matches  # noqa: E402
from onepr_strategy import ONEPR_STRATEGY_ID, save_onepr_strategy_prediction  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def run_onepr_for_queue(*, new_only: bool = False, limit: int = 0) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()

    matches = list_queued_matches(
        leagues_by_sport=cfg.leagues_by_sport,
        new_only=False,
        limit=limit or 0,
    )
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]

    print(f"[*] 1pr (#{ONEPR_STRATEGY_ID}): {len(matches)} matches in queue")
    ok = skip = fail = 0

    for idx, q in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {q.match_id} | {q.home_name} - {q.away_name}")
        if new_only:
            with get_db_connection() as conn:
                existing = conn.execute(
                    "SELECT prediction FROM strategy_predictions WHERE match_id=? AND strategy_id=?",
                    (q.match_id, ONEPR_STRATEGY_ID),
                ).fetchone()
            if existing and str(existing["prediction"] or "").strip():
                print("    [=] прогноз 1pr уже есть")
                skip += 1
                continue

        try:
            pred = save_onepr_strategy_prediction(q.match_id)
            if not pred:
                print("    [-] нет вероятностей «1 пр» или кф")
                skip += 1
                continue
            print(
                f"    [+] {pred.get('label')} ({pred['prediction']}) @ {pred.get('odds')} "
                f"p={float(pred.get('probability') or 0)*100:.1f}% "
                f"edge={float(pred.get('difference') or 0)*100:+.1f}pp"
            )
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(matches), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] 1pr: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="1pr strategy (#8) for DeluX")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_onepr_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
