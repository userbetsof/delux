"""DeluX — единая точка входа (Python вместо Excel/VBA UI)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)


def cmd_list(args) -> int:
    from matches_list import run as list_run

    return list_run(
        workbook_path=args.workbook or "",
        auto=args.auto,
        db_only=not args.excel,
    )


def cmd_analyze(args) -> int:
    from analyze_match import run_analyze

    new = args.new or (not args.all and not args.match_id)
    return run_analyze(
        workbook=args.workbook,
        match_id=args.match_id,
        new=new,
        all_matches=args.all,
        limit=args.limit,
    )


def cmd_pipeline(args) -> int:
    from run_pipeline import run_pipeline

    return run_pipeline(
        workbook=args.workbook,
        auto=args.auto,
        limit=args.limit,
        db_only=not args.excel,
    )


def cmd_check(args) -> int:
    from matches_check import run as check_run

    if not args.workbook and not args.db_only:
        print("[-] check: укажите --db-only или --workbook для legacy Excel-архива")
        return 1
    if args.db_only:
        from result_checker import run_db_check

        return run_db_check()
    return check_run(args.workbook)


def cmd_bts(args) -> int:
    from scripts.run_bts_strategy import run_bts_for_queue

    summary = run_bts_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_favorites(args) -> int:
    from scripts.run_favorites_strategy import run_favorites_for_queue

    summary = run_favorites_for_queue(
        new_only=args.new,
        limit=args.limit,
        fetch_injuries=not args.no_injuries,
    )
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_stavka_tv(args) -> int:
    from scripts.run_stavka_tv_strategy import run_stavka_tv_for_queue

    summary = run_stavka_tv_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_dogs(args) -> int:
    from scripts.run_dogs_strategy import run_dogs_for_queue

    summary = run_dogs_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_onepr(args) -> int:
    from scripts.run_onepr_strategy import run_onepr_for_queue

    summary = run_onepr_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_favorites_stats(args) -> int:
    from favorites_stats.report import build_report, print_summary, save_report
    from pathlib import Path

    report = build_report(
        db_path=args.db or None,
        favorite_leagues_only=args.all_leagues,
        odds_min=args.odds_min,
        odds_max=args.odds_max,
        odds_step=args.odds_step,
        fetch_injuries=args.fetch_injuries,
        fetch_injuries_limit=args.fetch_injuries_limit,
    )
    out = Path(args.out) if args.out else None
    saved = save_report(report, out)
    if not args.quiet:
        print_summary(report)
        print(f"Отчёт: {saved}")
    else:
        print(saved)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="DeluX IncoProrok — полный Python-пайплайн (БД + calc .xlsm)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Загрузить матчи с Flashscore в БД")
    p_list.add_argument(
        "--auto",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Все виды из DELUX_SPORTS_AUTO (по умолчанию: да, если их >1)",
    )
    p_list.add_argument("--excel", action="store_true", help="Dopolnitelno pisat list Spisok v Excel")
    p_list.add_argument("--workbook", default="", help="Путь к .xlsm (только с --excel)")

    p_an = sub.add_parser(
        "analyze",
        help="Анализ матчей в БД (стратегии #1–8 по умолчанию)",
    )
    p_an.add_argument("--match-id", default="")
    g = p_an.add_mutually_exclusive_group()
    g.add_argument("--new", action="store_true", help="Только матчи, которых нет в matches")
    g.add_argument("--all", action="store_true", help="Все из очереди")
    p_an.add_argument("--limit", type=int, default=0)
    p_an.add_argument("--workbook", default="", help="Переопределить CALC_WORKBOOK")

    p_pipe = sub.add_parser(
        "pipeline",
        help="list + analyze --new (все стратегии #1–8)",
    )
    p_pipe.add_argument(
        "--auto",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Все виды из DELUX_SPORTS_AUTO (по умолчанию: да, если их >1)",
    )
    p_pipe.add_argument("--limit", type=int, default=0)
    p_pipe.add_argument("--excel", action="store_true")
    p_pipe.add_argument("--workbook", default="")

    p_chk = sub.add_parser("check", help="Проверить результаты матчей")
    p_chk.add_argument("--db-only", action="store_true", help="Обновить matches в БД")
    p_chk.add_argument("--workbook", default="")

    p_bts = sub.add_parser("bts", help="Стратегия BTS (#4) для очереди")
    p_bts.add_argument("--new", action="store_true", help="Пропускать матчи с уже сохранённым BTS")
    p_bts.add_argument("--limit", type=int, default=0)

    p_fav_sig = sub.add_parser("favorites", help="Стратегия Favorites (#5) — победа фаворита")
    p_fav_sig.add_argument("--new", action="store_true")
    p_fav_sig.add_argument("--limit", type=int, default=0)
    p_fav_sig.add_argument("--no-injuries", action="store_true")

    p_fav = sub.add_parser("favorites-stats", help="Статистика ставок на фаворитов (без сигналов)")
    p_fav.add_argument("--db", default="", help="Путь к matches.db")
    p_fav.add_argument("--out", default="", help="JSON-отчёт")
    p_fav.add_argument("--all-leagues", action="store_true", help="Только избранные лиги из .env")
    p_fav.add_argument("--odds-min", type=float, default=1.1)
    p_fav.add_argument("--odds-max", type=float, default=4.0)
    p_fav.add_argument("--odds-step", type=float, default=0.1)
    p_fav.add_argument("--fetch-injuries", action="store_true")
    p_fav.add_argument("--fetch-injuries-limit", type=int, default=50)
    p_fav.add_argument("--quiet", action="store_true")

    p_stavka = sub.add_parser("stavka-tv", help="Стратегия StavkaTV (#6)")
    p_stavka.add_argument("--new", action="store_true")
    p_stavka.add_argument("--limit", type=int, default=0)

    p_dogs = sub.add_parser("dogs", help="Стратегия Moneyway (#7)")
    p_dogs.add_argument("--new", action="store_true")
    p_dogs.add_argument("--limit", type=int, default=0)

    p_onepr = sub.add_parser("onepr", help="Стратегия 1pr (#8) — макс. вероятность «1 пр»")
    p_onepr.add_argument("--new", action="store_true")
    p_onepr.add_argument("--limit", type=int, default=0)

    args = parser.parse_args()
    handlers = {
        "list": cmd_list,
        "analyze": cmd_analyze,
        "pipeline": cmd_pipeline,
        "check": cmd_check,
        "bts": cmd_bts,
        "favorites": cmd_favorites,
        "favorites-stats": cmd_favorites_stats,
        "stavka-tv": cmd_stavka_tv,
        "dogs": cmd_dogs,
        "onepr": cmd_onepr,
    }
    raise SystemExit(handlers[args.command](args))


if __name__ == "__main__":
    main()
