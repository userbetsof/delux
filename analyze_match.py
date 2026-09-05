"""CLI: анализ матчей из БД-очереди → calc .xlsm → matches.db."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

from match_analysis import analyze_match  # noqa: E402
from analysis_data import season_games_ready  # noqa: E402
from match_store import QueuedMatch, get_queued_match, list_queued_matches  # noqa: E402
from settings import DeluxSettings  # noqa: E402
from calc_backend import get_calc_engine  # noqa: E402
from db import create_database  # noqa: E402


def run_analyze(
    *,
    workbook: str = "",
    match_id: str = "",
    new: bool = False,
    all_matches: bool = False,
    limit: int = 0,
) -> int:
    cfg = DeluxSettings.from_env()
    calc_workbook = workbook or cfg.resolve_calc_workbook()
    create_database()

    if match_id:
        mid = match_id.strip()
        queued = get_queued_match(mid)
        if queued:
            matches = [queued]
        else:
            from analysis_data import detect_sport_from_match_page

            detected = detect_sport_from_match_page(mid)
            sport = detected or cfg.sport
            matches = [QueuedMatch(match_id=mid, sport=sport)]
    else:
        matches = list_queued_matches(
            leagues_by_sport=cfg.leagues_by_sport,
            new_only=new and not all_matches,
            limit=limit or int(os.environ.get("ANALYZE_LIMIT", "0") or 0),
        )
        # Доп. отсев: только избранные лиги по каждому виду (1/4/3).
        before = len(matches)
        matches = [
            q
            for q in matches
            if cfg.is_favorite_league(q.sport, q.tour_name)
        ]
        skipped = before - len(matches)
        if skipped:
            print(f"[*] Пропущено вне избранных лиг: {skipped}")

    if not matches:
        if new and not all_matches and not match_id:
            total = len(
                list_queued_matches(
                    leagues_by_sport=cfg.leagues_by_sport,
                    new_only=False,
                )
            )
            pending = len(
                list_queued_matches(
                    leagues_by_sport=cfg.leagues_by_sport,
                    new_only=True,
                )
            )
            if total:
                print(
                    f"[+] Нет матчей для анализа: в очереди {total}, "
                    f"ожидают анализа {pending} (полный анализ уже есть у остальных)"
                )
            else:
                print("[+] Нет матчей для анализа (запустите: py delux.py list)")
        else:
            print("[+] Нет матчей для анализа (запустите: py delux.py list)")
        return 0

    for sid in sorted({q.sport for q in matches}):
        fav = cfg.leagues_for_sport(sid)
        print(f"[*] sport={sid} избранные: {fav if fav is not None else 'ALL'}")

    arbworld_index = None
    if any(int(q.sport or 1) == 1 for q in matches):
        try:
            from dogs_strategy import get_arbworld_index

            from dogs_strategy import _dogs_root, last_arbworld_error

            print(f"[*] Moneyway (#7): DOGS_ROOT={_dogs_root()}")
            arbworld_index = get_arbworld_index()
            if arbworld_index is not None:
                print(f"[*] Moneyway (#7): Arbworld runners={len(arbworld_index)}")
            else:
                reason = last_arbworld_error() or "unknown"
                print(f"[!] Moneyway (#7): skip — {reason}")
        except Exception as exc:
            print(f"[!] Moneyway (#7): Arbworld fetch failed — {exc}")

    print("[*] Strategies on analyze: #1-3 calc, #4 BTS, #5 Favorites, #6 StavkaTV, #7 Moneyway, #8 1pr")

    ok = 0
    with get_calc_engine(cfg) as engine:
        for idx, queued in enumerate(matches, 1):
            match = queued.to_match_info()
            ms = cfg.match_settings
            if queued.sport:
                from analysis_data import build_settings, season_games_ready

                ms = build_settings(
                    sport=queued.sport,
                    source=cfg.source,
                    tz_base=cfg.tz_base,
                    dayzone_base=cfg.dayzone_base,
                    time_offset=cfg.time_offset,
                )
            print(f"\n[{idx}/{len(matches)}] {match.match_id} | {match.league} | {match.home} - {match.away}")
            ready, reason = season_games_ready(
                ms,
                match.match_id,
                match.home,
                match.away,
                min_games=cfg.min_tour_games,
            )
            if not ready:
                print(f"[!] Пропуск: {reason}")
                continue
            try:
                analyze_match(
                    calc_workbook,
                    match,
                    ms,
                    queued=queued,
                    engine=engine,
                    arbworld_index=arbworld_index,
                )
                ok += 1
                print(f"[+] Сохранено в БД: {match.match_id}")
            except Exception as exc:
                print(f"[-] Ошибка {match.match_id}: {exc}")

    print(f"\n[+] Готово: {ok}/{len(matches)}")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="Python-анализ DeluX")
    parser.add_argument("--workbook", default="")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--match-id")
    group.add_argument("--new", action="store_true")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        run_analyze(
            workbook=args.workbook,
            match_id=args.match_id or "",
            new=args.new,
            all_matches=args.all,
        )
    )


if __name__ == "__main__":
    main()
