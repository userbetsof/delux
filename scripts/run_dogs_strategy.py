"""Moneyway / Dogs strategy (#7) для очереди DeluX."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import create_database, get_db_connection, upsert_moneyway, upsert_strategy_prediction  # noqa: E402
from dogs_strategy import (  # noqa: E402
    DOGS_STRATEGY_ID,
    build_moneyway_snapshot,
    fetch_arbworld_index,
)
from match_store import list_matches_for_strategy  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def run_dogs_for_queue(*, new_only: bool = False, limit: int = 0, sport: int = 1) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()

    matches = list_matches_for_strategy(
        sport=sport,
        leagues_by_sport=cfg.leagues_by_sport,
    )
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]
    if limit > 0:
        matches = matches[:limit]

    print(f"[*] Moneyway (#{DOGS_STRATEGY_ID}): {len(matches)} football matches")
    ok = skip = fail = saved_snap = 0

    try:
        arbworld_index = fetch_arbworld_index()
        print(f"    Arbworld runners: {len(arbworld_index)}")
    except Exception as exc:
        print(f"[-] Arbworld fetch failed: {exc}")
        return {"total": len(matches), "ok": 0, "skip": 0, "fail": 1}

    for idx, q in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {q.match_id} | {q.home_name} - {q.away_name}")
        try:
            snap = build_moneyway_snapshot(
                q.home_name,
                q.away_name,
                sport=q.sport,
                arbworld_index=arbworld_index,
            )
            if snap:
                upsert_moneyway(q.match_id, snap)
                saved_snap += 1

            if new_only:
                with get_db_connection() as conn:
                    existing = conn.execute(
                        "SELECT prediction FROM strategy_predictions WHERE match_id=? AND strategy_id=?",
                        (q.match_id, DOGS_STRATEGY_ID),
                    ).fetchone()
                if existing and str(existing["prediction"] or "").strip():
                    print("    [=] прогноз уже есть")
                    skip += 1
                    continue

            if not snap or not snap.get("has_signal") or not snap.get("signal_side"):
                print("    [-] нет moneyway-сигнала" + (" (snapshot ok)" if snap and snap.get("found") else ""))
                skip += 1
                continue

            upsert_strategy_prediction(
                q.match_id,
                DOGS_STRATEGY_ID,
                snap["signal_side"],
                odds=snap.get("signal_odds"),
                notes=snap.get("notes") or snap.get("raw_json"),
            )
            print(f"    [+] {snap['signal_side']} @ {snap.get('signal_odds')}")
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(matches), "ok": ok, "skip": skip, "fail": fail, "snapshots": saved_snap}
    print(f"\n[+] Moneyway: signals={ok} snapshots={saved_snap} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Moneyway/Dogs strategy (#7)")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_dogs_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
