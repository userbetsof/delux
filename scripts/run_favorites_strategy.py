"""Пересчёт Favorites (#5) для матчей из очереди DeluX."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from favorites_stats.injuries import fetch_and_store_for_match  # noqa: E402
from favorites_strategy import FAVORITES_STRATEGY_ID, compute_favorites_win_prediction  # noqa: E402
from db import create_database, get_db_connection, upsert_strategy_prediction  # noqa: E402
from match_store import list_queued_matches  # noqa: E402
from odds_service import build_fallback_odds, load_odds  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def run_favorites_for_queue(
    *,
    new_only: bool = False,
    limit: int = 0,
    fetch_injuries: bool = True,
) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()

    matches = list_queued_matches(
        leagues_by_sport=cfg.leagues_by_sport,
        new_only=False,
        limit=limit or 0,
    )
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]

    print(f"[*] Favorites (#{FAVORITES_STRATEGY_ID}): {len(matches)} matches in queue")
    ok = skip = fail = 0

    for idx, q in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {q.match_id} | {q.tour_name} | {q.home_name} - {q.away_name}")
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT prediction FROM strategy_predictions WHERE match_id = ? AND strategy_id = ?",
                (q.match_id, FAVORITES_STRATEGY_ID),
            ).fetchone()
        if new_only and existing and str(existing["prediction"] or "").strip():
            print("    [=] прогноз Favorites уже есть")
            skip += 1
            continue

        if fetch_injuries:
            try:
                inj = fetch_and_store_for_match(q.match_id)
                if inj.get("players"):
                    print(f"    injuries: {inj['players']} absent")
            except Exception as exc:
                print(f"    [!] injuries: {exc}")

        code, odds_data = load_odds(q.match_id, cfg.source)
        if code != 0 or odds_data is None:
            odds_data = build_fallback_odds(q.match_id)

        queue_odds = None
        if q.current_home or q.current_away:
            queue_odds = (q.current_home, q.current_draw, q.current_away)
        elif q.start_home or q.start_away:
            queue_odds = (q.start_home, q.start_draw, q.start_away)

        try:
            fav = compute_favorites_win_prediction(
                q.match_id,
                q.sport,
                odds_data=odds_data,
                odds_home=queue_odds[0] if queue_odds else None,
                odds_away=queue_odds[2] if queue_odds else None,
            )
            if not fav:
                print("    [-] кф вне диапазона или нет фаворита")
                skip += 1
                continue
            upsert_strategy_prediction(
                q.match_id,
                FAVORITES_STRATEGY_ID,
                fav["prediction"],
                odds=fav.get("odds"),
                notes=fav.get("notes"),
            )
            band = fav.get("odds_range") or {}
            print(
                f"    [+] {fav.get('label')} @ {fav.get('odds')} "
                f"range={band.get('min')}–{band.get('max')}"
            )
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(matches), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] Favorites: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Favorites strategy (#5) for DeluX queue")
    parser.add_argument("--new", action="store_true", help="Пропускать матчи с уже сохранённым прогнозом")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-injuries", action="store_true", help="Не загружать травмы")
    args = parser.parse_args()
    summary = run_favorites_for_queue(
        new_only=args.new,
        limit=args.limit,
        fetch_injuries=not args.no_injuries,
    )
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
