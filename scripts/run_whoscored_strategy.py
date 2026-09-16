"""WhoScored strategy (#9): точный счёт + фора для избранных лиг."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import create_database, get_db_connection, load_team_name_map, upsert_strategy_prediction  # noqa: E402
from match_store import list_matches_for_strategy  # noqa: E402
from odds_service import build_fallback_odds, load_odds  # noqa: E402
from settings import DeluxSettings  # noqa: E402
from whoscored_strategy import (  # noqa: E402
    WHOSCORED_STRATEGY_ID,
    build_whoscored_signal,
    last_whoscored_error,
    load_whoscored_index,
    match_preview_to_delux,
    save_whoscored_card,
)


def run_whoscored_for_queue(*, new_only: bool = False, limit: int = 0) -> dict:
    cfg = DeluxSettings.from_env()
    create_database()
    leagues = cfg.leagues_for_sport(1)

    matches = list_matches_for_strategy(sport=1, leagues_by_sport=cfg.leagues_by_sport)
    matches = [q for q in matches if cfg.is_favorite_league(q.sport, q.tour_name)]
    if limit > 0:
        matches = matches[:limit]

    print(f"[*] WhoScored (#{WHOSCORED_STRATEGY_ID}): {len(matches)} football matches")
    previews = load_whoscored_index(leagues, force=True)
    if previews is None:
        print(f"[-] WhoScored fetch failed: {last_whoscored_error()}")
        return {"total": len(matches), "ok": 0, "skip": 0, "fail": 1}
    print(f"    previews in favorite leagues: {len(previews)}")

    db_map = load_team_name_map("whoscored")
    ok = skip = fail = 0

    for idx, prev in enumerate(previews, 1):
        q = match_preview_to_delux(prev, matches, db_map)
        print(
            f"\n[{idx}/{len(previews)}] {prev.league_delux} | "
            f"{prev.home} {prev.score_home}:{prev.score_away} {prev.away}"
        )
        if not q:
            print("    [-] нет матча DeluX")
            skip += 1
            continue
        save_whoscored_card(q.match_id, prev)
        if new_only:
            with get_db_connection() as conn:
                existing = conn.execute(
                    "SELECT prediction FROM strategy_predictions WHERE match_id=? AND strategy_id=?",
                    (q.match_id, WHOSCORED_STRATEGY_ID),
                ).fetchone()
            if existing and str(existing["prediction"] or "").strip():
                print(f"    [=] уже есть для {q.match_id}")
                skip += 1
                continue

        from analysis_data import build_settings

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
            sig = build_whoscored_signal(prev, match_id=q.match_id, odds_data=odds_data)
            if not sig:
                print("    [i] extras сохранены, нет CS+AH")
                skip += 1
                continue
            upsert_strategy_prediction(
                q.match_id,
                WHOSCORED_STRATEGY_ID,
                sig["prediction"],
                odds=sig.get("odds"),
                notes=sig.get("notes"),
            )
            print(
                f"    [+] {q.match_id} {q.home_name}-{q.away_name} "
                f"{sig['prediction']} cs@{sig.get('cs_odds')} ah@{sig.get('ah_odds')}"
            )
            ok += 1
        except Exception as exc:
            print(f"    [-] {exc}")
            fail += 1

    summary = {"total": len(previews), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] WhoScored: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="WhoScored strategy (#9)")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_whoscored_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
