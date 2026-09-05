"""CLI: сбор статистики ставок на фаворитов."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from favorites_stats.report import build_report, print_summary, save_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DeluX favorites_stats — статистика кф победы и форы фаворита",
    )
    parser.add_argument("--db", default="", help="Путь к matches.db")
    parser.add_argument("--out", default="", help="JSON-отчёт (по умолчанию data/favorites_stats_report.json)")
    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="Фильтровать только избранные лиги из .env (по умолчанию — все лиги в БД)",
    )
    parser.add_argument("--odds-min", type=float, default=1.1)
    parser.add_argument("--odds-max", type=float, default=4.0)
    parser.add_argument("--odds-step", type=float, default=0.1)
    parser.add_argument(
        "--fetch-injuries",
        action="store_true",
        help="Загрузить missingPlayers из Flashscore pq_graphql (_hash=dmpe2)",
    )
    parser.add_argument(
        "--fetch-injuries-limit",
        type=int,
        default=50,
        help="Макс. матчей для загрузки травм за один запуск",
    )
    parser.add_argument("--quiet", action="store_true", help="Только путь к JSON, без сводки")
    args = parser.parse_args()

    db_path = args.db.strip() or None
    out_path = Path(args.out) if args.out.strip() else None

    report = build_report(
        db_path=db_path,
        favorite_leagues_only=args.all_leagues,
        odds_min=args.odds_min,
        odds_max=args.odds_max,
        odds_step=args.odds_step,
        fetch_injuries=args.fetch_injuries,
        fetch_injuries_limit=args.fetch_injuries_limit,
    )
    saved = save_report(report, out_path)

    if args.quiet:
        print(saved)
    else:
        print_summary(report)
        print(f"Отчёт: {saved}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
