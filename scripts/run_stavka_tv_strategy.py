"""StavkaTV strategy (#6) для очереди DeluX."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import create_database, get_db_connection, upsert_strategy_prediction  # noqa: E402
from match_store import list_matches_for_strategy  # noqa: E402
from settings import DeluxSettings  # noqa: E402
from stavka_tv_strategy import (  # noqa: E402
    STAVKA_TV_STRATEGY_ID,
    compute_stavka_tv_prediction,
    stavka_db_path,
)


def run_stavka_tv_for_queue(*, new_only: bool = False, limit: int = 0) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()
    db = stavka_db_path()
    if not db.is_file():
        print(f"[-] StavkaTV DB не найдена: {db}")
        return {"total": 0, "ok": 0, "skip": 0, "fail": 1}

    matches = list_matches_for_strategy(leagues_by_sport=cfg.leagues_by_sport)
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]
    if limit > 0:
        matches = matches[:limit]

    print(f"[*] StavkaTV (#{STAVKA_TV_STRATEGY_ID}): {len(matches)} matches, db={db}")
    ok = skip = fail = 0

    for idx, q in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {q.match_id} | {q.home_name} - {q.away_name}")
        if new_only:
            with get_db_connection() as conn:
                existing = conn.execute(
                    "SELECT prediction FROM strategy_predictions WHERE match_id=? AND strategy_id=?",
                    (q.match_id, STAVKA_TV_STRATEGY_ID),
                ).fetchone()
            if existing and str(existing["prediction"] or "").strip():
                print("    [=] прогноз уже есть")
                skip += 1
                continue

        try:
            pred = compute_stavka_tv_prediction(
                q.match_id,
                q.home_name,
                q.away_name,
                q.sport,
            )
            if not pred:
                print("    [-] нет прогноза stavka.tv")
                skip += 1
                continue
            upsert_strategy_prediction(
                q.match_id,
                STAVKA_TV_STRATEGY_ID,
                pred["prediction"],
                odds=pred.get("odds"),
                notes=pred.get("notes"),
            )
            print(f"    [+] {pred['prediction']} @ {pred.get('odds')}")
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(matches), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] StavkaTV: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="StavkaTV strategy (#6)")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_stavka_tv_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
