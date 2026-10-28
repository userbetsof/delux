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
    from result_checker import run_db_check

    if args.workbook:
        from matches_check import run as check_run

        return check_run(args.workbook)
    return run_db_check()


def cmd_calc_check(args) -> int:
    from scripts.compare_strategies import main as calc_check_main
    import sys as _sys

    saved = _sys.argv[:]
    argv = ["compare_strategies.py"]
    if args.match_id:
        argv.append(args.match_id)
    if args.excel:
        argv.append("--excel")
    argv.extend(["--tol", str(args.tol)])
    _sys.argv = argv
    try:
        return calc_check_main()
    finally:
        _sys.argv = saved


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


def cmd_whoscored(args) -> int:
    from scripts.run_whoscored_strategy import run_whoscored_for_queue

    summary = run_whoscored_for_queue(new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_match_info(args) -> int:
    from scripts.run_match_info import run_match_info

    summary = run_match_info(match_id=args.match_id, new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


def cmd_ml_train(args) -> int:
    from src.ml.train import train_models

    models = [args.model] if args.model else None
    targets = [args.target] if args.target else None
    train_models(config_path=args.config or None, models=models, targets=targets, limit=args.limit)
    return 0


def cmd_ml_predict(args) -> int:
    from src.ml.predict import predict_matches

    predict_matches(
        config_path=args.config or None,
        run_id=args.run_id,
        model_type=args.model,
        match_id=args.match_id,
    )
    return 0


def cmd_mlflow_ui(args) -> int:
    import subprocess
    import sys

    from src.ml.config import artifacts_dir, load_config, tracking_uri

    config = load_config(args.config or None)
    artifacts_dir(config).mkdir(parents=True, exist_ok=True)
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "mlflow",
            "ui",
            "--backend-store-uri",
            tracking_uri(config),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
    )


def cmd_archive(args) -> int:
    from archive_matches import archive_match, archive_date, archive_days

    if args.match_id:
        result = archive_match(args.match_id, args.sport)
        print(f"\n[RESULT] Match {args.match_id}: saved={result['saved']}")
        print(f"  Success: {result['feeds_success']}")
        print(f"  Failed: {result['feeds_failed']}")
        return 0 if result['saved'] else 1

    elif args.date:
        results = archive_date(args.date, args.sport)
        print(f"\n[SUMMARY] Archived {len(results)} matches for {args.date}")
        return 0

    elif args.days:
        results = archive_days(args.days, args.sport)
        print(f"\n[SUMMARY] Archived {len(results)} matches for last {args.days} days")
        return 0

    return 1


def cmd_ratings(args) -> int:
    from ratings import (
        update_glicko2_for_match,
        recalculate_all_glicko2,
        get_all_glicko2,
    )

    if args.ratings_command == "update":
        result = update_glicko2_for_match(args.match_id)
        if result:
            print(f"[GLICKO2] Match {result['match_id']}:")
            print(f"  {result['home_team']} vs {result['away_team']}")
            print(f"  Score: {result['score_home']} - {result['score_away']}")
            print(f"  Rating before: {result['glicko2_before']}")
            print(f"  Rating after: {result['glicko2_after']}")
            print(f"  Expected: {result['expected']}")
            print(f"  Delta: {result['delta']}")
        else:
            print("[GLICKO2] No data or match not finished")
        return 0

    elif args.ratings_command == "recalculate":
        result = recalculate_all_glicko2(args.sport)
        print(f"[GLICKO2] Recalculated: {result['teams_processed']} teams, {result['matches_processed']} matches")
        print(f"  Duration: {result['duration_ms']}ms")
        return 0

    elif args.ratings_command == "list":
        result = get_all_glicko2(args.sport)
        print(f"\n[GLICKO2] Top {min(20, result['total'])} teams:")
        print(f"{'Rank':<6} {'Team':<25} {'Sport':<8} {'Rating':<10} {'RD':<8} {'Played':<8}")
        print("-" * 65)
        for i, item in enumerate(result["items"][:20], 1):
            print(f"{i:<6} {item['team_name']:<25} {item['sport']:<8} "
                  f"{item['rating']:<10.2f} {item['rd']:<8.2f} {item['matches_played']:<8}")
        return 0

    return 1


def cmd_venues(args) -> int:
    from venues import (
        geocode_and_save_venues,
        calculate_all_distances,
        analyze_distance_impact,
        print_distance_analysis,
        add_distance_to_features,
        populate_match_distances,
    )

    if args.venues_command == "geocode":
        stats = geocode_and_save_venues(args.batch)
        print(f"\n[RESULT] Geocoding: {stats['geocoded']} geocoded, {stats['failed']} failed")
        return 0

    elif args.venues_command == "distances":
        stats = calculate_all_distances()
        print(f"\n[RESULT] Distances: {stats['calculated']} calculated, {stats['skipped']} skipped")
        return 0

    elif args.venues_command == "match-distances":
        match_ids = [args.match_id] if args.match_id else None
        count = populate_match_distances(match_ids)
        print(f"\n[RESULT] Match distances: {count} populated")
        return 0

    elif args.venues_command == "analysis":
        analysis = analyze_distance_impact()
        print_distance_analysis(analysis)
        return 0

    elif args.venues_command == "all":
        print("\n" + "="*60)
        print("[STEP 1] Geocoding venues...")
        print("="*60)
        geo_stats = geocode_and_save_venues()

        print("\n" + "="*60)
        print("[STEP 2] Calculating distances...")
        print("="*60)
        dist_stats = calculate_all_distances()

        print("\n" + "="*60)
        print("[STEP 3] Analyzing distance impact...")
        print("="*60)
        analysis = analyze_distance_impact()
        print_distance_analysis(analysis)

        print(f"\n{'='*60}")
        print("[COMPLETE]")
        print(f"{'='*60}")
        print(f"Geocoded: {geo_stats['geocoded']}")
        print(f"Distances calculated: {dist_stats['calculated']}")
        return 0

    elif args.venues_command == "feature":
        add_distance_to_features()
        return 0

    return 1


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
        description="DeluX IncoProrok — Python-пайплайн (Flashscore + SQLite, без Excel)",
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
        help="Анализ матчей в БД (стратегии #1–9 по умолчанию)",
    )
    p_an.add_argument("--match-id", default="")
    g = p_an.add_mutually_exclusive_group()
    g.add_argument("--new", action="store_true", help="Только матчи, которых нет в matches")
    g.add_argument("--all", action="store_true", help="Все из очереди")
    p_an.add_argument("--limit", type=int, default=0)
    p_an.add_argument("--workbook", default="", help="Переопределить CALC_WORKBOOK")

    p_pipe = sub.add_parser(
        "pipeline",
        help="list + check + analyze --new (все стратегии #1–9)",
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
    p_chk.add_argument("--db-only", action="store_true", help="Только БД (по умолчанию)")
    p_chk.add_argument("--workbook", default="", help="Legacy: Excel-архив")

    p_calc = sub.add_parser(
        "calc-check",
        help="Python-calc: NTB/Betalone/Sniper + 10 подстратегий (допуск 1%%)",
    )
    p_calc.add_argument("match_id", nargs="?", default="")
    p_calc.add_argument("--excel", action="store_true", help="Опционально сравнить с Excel COM")
    p_calc.add_argument("--tol", type=float, default=0.01)

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

    p_ws = sub.add_parser("whoscored", help="Стратегия WhoScored (#9) — точный счёт + фора")
    p_ws.add_argument("--new", action="store_true")
    p_ws.add_argument("--limit", type=int, default=0)

    p_info = sub.add_parser("match-info", help="Снимок инфо о матче: стадион, судья, зрители")
    p_info.add_argument("--match-id", default="")
    p_info.add_argument("--new", action="store_true", help="Только матчи без снимка")
    p_info.add_argument("--limit", type=int, default=0)

    p_ml_train = sub.add_parser("ml-train", help="Обучить XGBoost и CatBoost с MLflow")
    p_ml_train.add_argument("--config", default="")
    p_ml_train.add_argument("--model", choices=("xgboost", "catboost"), default="")
    p_ml_train.add_argument("--target", choices=("1x2", "over_2_5"), default="")
    p_ml_train.add_argument("--limit", type=int, default=0)

    p_ml_predict = sub.add_parser("ml-predict", help="ML-прогнозы для будущих матчей")
    p_ml_predict.add_argument("--config", default="")
    p_ml_predict.add_argument("--run-id", default="")
    p_ml_predict.add_argument("--model", choices=("xgboost", "catboost"), default="")
    p_ml_predict.add_argument("--match-id", default="")

    p_mlflow = sub.add_parser("mlflow-ui", help="Локальный интерфейс MLflow")
    p_mlflow.add_argument("--config", default="")
    p_mlflow.add_argument("--host", default="127.0.0.1")
    p_mlflow.add_argument("--port", type=int, default=5001)

    p_archive = sub.add_parser("archive", help="Архивация исторических матчей")
    p_archive.add_argument("--match-id", default="", help="Flashscore match ID")
    p_archive.add_argument("--date", default="", help="Дата в формате YYYY.MM.DD")
    p_archive.add_argument("--days", type=int, default=0, help="Количество дней назад")
    p_archive.add_argument("--sport", type=int, default=1, help="ID вида спорта (1=Football)")

    p_venues = sub.add_parser("venues", help="Управление стадионами и расстояниями")
    p_venues_sub = p_venues.add_subparsers(dest="venues_command", required=True)
    
    p_venues_geo = p_venues_sub.add_parser("geocode", help="Геокодирование стадионов без координат")
    p_venues_geo.add_argument("--batch", type=int, default=50, help="Размер батча (по умолчанию: 50)")
    
    p_venues_dist = p_venues_sub.add_parser("distances", help="Расчёт всех расстояний между стадионами")
    
    p_venues_ana = p_venues_sub.add_parser("analysis", help="Анализ влияния расстояния на результаты")
    
    p_venues_all = p_venues_sub.add_parser("all", help="Геокодирование + расчёт расстояний + анализ")
    
    p_venues_feat = p_venues_sub.add_parser("feature", help="Добавить distance как фичу в XGBoost")
    
    p_venues_match = p_venues_sub.add_parser("match-distances", help="Заполнить distance для матчей")
    p_venues_match.add_argument("--match-id", default="", help="Конкретный match_id (опционально)")

    # ratings
    p_ratings = sub.add_parser("ratings", help="Glicko-2 рейтинги")
    p_ratings_sub = p_ratings.add_subparsers(dest="ratings_command", required=True)
    
    p_ratings_update = p_ratings_sub.add_parser("update", help="Обновить Glicko-2 для матча")
    p_ratings_update.add_argument("--match-id", required=True)
    
    p_ratings_recalc = p_ratings_sub.add_parser("recalculate", help="Пересчитать все рейтинги")
    p_ratings_recalc.add_argument("--sport", type=int, default=None)
    
    p_ratings_list = p_ratings_sub.add_parser("list", help="Список рейтингов")
    p_ratings_list.add_argument("--sport", type=int, default=None)

    args = parser.parse_args()
    handlers = {
        "list": cmd_list,
        "analyze": cmd_analyze,
        "pipeline": cmd_pipeline,
        "check": cmd_check,
        "calc-check": cmd_calc_check,
        "bts": cmd_bts,
        "favorites": cmd_favorites,
        "favorites-stats": cmd_favorites_stats,
        "stavka-tv": cmd_stavka_tv,
        "dogs": cmd_dogs,
        "onepr": cmd_onepr,
        "whoscored": cmd_whoscored,
        "match-info": cmd_match_info,
        "ml-train": cmd_ml_train,
        "ml-predict": cmd_ml_predict,
        "mlflow-ui": cmd_mlflow_ui,
        "archive": cmd_archive,
        "venues": cmd_venues,
        "ratings": cmd_ratings,
    }
    raise SystemExit(handlers[args.command](args))


if __name__ == "__main__":
    main()
