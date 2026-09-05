"""Пересчёт BTS (strategy #4) для матчей из очереди DeluX."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import build_settings  # noqa: E402
from bts_strategy import BTS_STRATEGY_ID, compute_bts_prediction  # noqa: E402
from db import create_database, get_db_connection, upsert_strategy_prediction  # noqa: E402
from match_store import list_queued_matches  # noqa: E402
from odds_service import build_fallback_odds, load_odds  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def run_bts_for_queue(
    *,
    new_only: bool = False,
    limit: int = 0,
    sport: int = 1,
) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()

    matches = list_queued_matches(
        leagues_by_sport=cfg.leagues_by_sport,
        sport=sport,
        new_only=False,
        limit=limit or 0,
    )
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]

    print(f"[*] BTS (#{BTS_STRATEGY_ID}): {len(matches)} football matches in queue")
    ok = skip = fail = 0

    for idx, q in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {q.match_id} | {q.tour_name} | {q.home_name} - {q.away_name}")
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT prediction FROM strategy_predictions WHERE match_id = ? AND strategy_id = ?",
                (q.match_id, BTS_STRATEGY_ID),
            ).fetchone()
        if new_only and existing and str(existing["prediction"] or "").strip():
            print("    [=] прогноз BTS уже есть")
            skip += 1
            continue

        settings = build_settings(
            sport=q.sport,
            source=cfg.source,
            tz_base=cfg.tz_base,
            dayzone_base=cfg.dayzone_base,
            time_offset=cfg.time_offset,
        )
        code, odds_data = load_odds(q.match_id, settings.source)
        if code != 0 or odds_data is None:
            odds_data = build_fallback_odds(q.match_id)

        try:
            bts = compute_bts_prediction(
                q.match_id,
                q.home_name,
                q.away_name,
                settings,
                odds_data=odds_data,
            )
            if not bts:
                print("    [-] условие 2/2 не выполнено или нет кф ОЗ")
                skip += 1
                continue
            upsert_strategy_prediction(
                q.match_id,
                BTS_STRATEGY_ID,
                bts["prediction"],
                odds=bts.get("odds"),
                notes=bts.get("notes"),
            )
            print(
                f"    [+] {bts['prediction']} @ {bts.get('odds')} "
                f"rate={float(bts.get('btts_rate') or 0)*100:.0f}%"
            )
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(matches), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] BTS: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="BTS strategy (#4) for DeluX queue")
    parser.add_argument("--new", action="store_true", help="Пропускать матчи с уже сохранённым BTS")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_bts_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
