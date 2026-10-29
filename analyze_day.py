"""Анализ матчей конкретного дня (сдвиг от сегодня от -7 до +7).

Параметр ленты дня f_{sport}_{dz}_{tz}_{suffix} — это ПРЯМОЙ сдвиг дня
от сегодняшнего, и он работает в обе стороны:

    dz = 0  → сегодня
    dz = 1  → завтра      dz = -1 → вчера
    dz = 3  → через 3 дня dz = -3 → 3 дня назад

(Проверено: f_1_-1_-7_ru_1 отдаёт матчи за 28.10, f_1_1_-7_ru_1 — за 30.10.)

ВАЖНО: cfg.dayzone_base (=8) и cfg.dayzone (=0) — это НЕ дни ленты.
Они относятся к настройке Excel-старта (Старт!V2), где 8 = сегодня.
Поэтому здесь dz передаётся напрямую как offset.

    py -3 analyze_day.py --offset 0               # сегодня
    py -3 analyze_day.py --offset -1              # вчера
    py -3 analyze_day.py --offset 2 --sport 4     # хоккей через 2 дня
    py -3 analyze_day.py --offset -3 --list-only  # только показать
    py -3 analyze_day.py --offset 1 --strategies 1,3 --no-fail-fast
    py -3 analyze_day.py --offset 0 --all-leagues # все лиги дня
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

MAX_OFFSET = 7


def day_label(offset: int) -> str:
    """Человеческая подпись дня и его дата."""
    date = (datetime.now() + timedelta(days=offset)).strftime("%Y.%m.%d")
    if offset == 0:
        return f"сегодня ({date})"
    if offset == -1:
        return f"вчера ({date})"
    if offset == 1:
        return f"завтра ({date})"
    if offset < -1:
        return f"{abs(offset)} дн. назад ({date})"
    return f"через {offset} дн. ({date})"


def validate_offset(offset: int) -> str:
    if not (-MAX_OFFSET <= offset <= MAX_OFFSET):
        return (
            f"сдвиг должен быть от -{MAX_OFFSET} до +{MAX_OFFSET} "
            f"(получено {offset})"
        )
    return ""


def fetch_day_matches(offset: int, sport: int, *, all_leagues: bool = False):
    """Матчи дня из ленты f_ (dayzone = offset напрямую)."""
    from analysis_data import build_settings
    from matches_list import _fetch_sport_matches
    from match_store import filter_matches_for_queue
    from settings import DeluxSettings

    cfg = DeluxSettings.from_env()
    ms = build_settings(
        sport=sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )

    matches = _fetch_sport_matches(
        sport,
        ms.sourcer,
        ms.suffix,
        cfg.timezone,
        offset,
        cfg.time_offset,
    )
    print(f"[*] В ленте дня: {len(matches)}")

    leagues = None if all_leagues else cfg.leagues_for_sport(sport)
    kept, skip_league, skip_tour = filter_matches_for_queue(
        matches,
        sport,
        leagues=leagues,
        min_games=cfg.min_tour_games,
        settings=ms,
    )
    if skip_league or skip_tour:
        print(
            f"[*] отсеяно: лиг={skip_league}, тур<{cfg.min_tour_games}={skip_tour}"
        )
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Анализ матчей конкретного дня (-{MAX_OFFSET}..+{MAX_OFFSET})"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help=f"сдвиг дня от сегодня: -{MAX_OFFSET}..+{MAX_OFFSET} (0 = сегодня)",
    )
    parser.add_argument(
        "--sport", type=int, default=0, help="вид спорта (по умолчанию из настроек)"
    )
    parser.add_argument("--list-only", action="store_true", help="только показать матчи")
    parser.add_argument("--strategies", default="", help="all или номера через запятую")
    parser.add_argument("--no-fail-fast", action="store_true", help="не прерываться при ошибке")
    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="не отсеивать по избранным лигам (все лиги дня)",
    )
    args = parser.parse_args()

    err = validate_offset(args.offset)
    if err:
        print(f"[-] {err}")
        return 2

    from settings import DeluxSettings

    cfg = DeluxSettings.from_env()
    sport = args.sport or cfg.sport

    print(f"[*] День: {day_label(args.offset)} | sport={sport} dayzone={args.offset}")

    try:
        kept = fetch_day_matches(args.offset, sport, all_leagues=args.all_leagues)
    except Exception as exc:  # noqa: BLE001
        print(f"[-] лента дня недоступна: {exc}")
        return 1

    print(f"[*] К анализу: {len(kept)}")
    if not kept:
        print("[!] На этот день матчей нет (или все отсеяны фильтром)")
        if not args.all_leagues:
            print("    Попробуйте --all-leagues (все лиги дня)")
        return 0

    if args.list_only:
        for m in kept:
            print(
                f"    {str(m.get('date_match') or ''):16} "
                f"{str(m.get('tour_name') or ''):28} "
                f"{m.get('home_name', '')} - {m.get('away_name', '')}"
            )
        return 0

    from analyze_match import _coerce_strategies, run_analyze
    from match_store import upsert_matches

    written = upsert_matches(kept, sport, leagues=cfg.leagues_for_sport(sport))
    print(f"[+] В очередь записано: {written}")

    ids = [m["match_id"] for m in kept if m.get("match_id")]
    return run_analyze(
        match_ids=ids,
        only_strategies=_coerce_strategies(args.strategies),
        fail_fast=not args.no_fail_fast,
    )


if __name__ == "__main__":
    sys.exit(main())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Анализ матчей конкретного дня (-{MAX_OFFSET}..+{MAX_OFFSET})"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help=f"сдвиг дня от сегодня: -{MAX_OFFSET}..+{MAX_OFFSET} (0 = сегодня)",
    )
    parser.add_argument(
        "--sport", type=int, default=0, help="вид спорта (по умолчанию из настроек)"
    )
    parser.add_argument("--list-only", action="store_true", help="только показать матчи")
    parser.add_argument("--strategies", default="", help="all или номера через запятую")
    parser.add_argument("--no-fail-fast", action="store_true", help="не прерываться при ошибке")
    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="не отсеивать по избранным лигам (все лиги дня)",
    )
    args = parser.parse_args()

    err = validate_offset(args.offset)
    if err:
        print(f"[-] {err}")
        return 2

    from settings import DeluxSettings

    cfg = DeluxSettings.from_env()
    sport = args.sport or cfg.sport

    print(f"[*] День: {day_label(args.offset)} | sport={sport}")

    try:
        kept = fetch_day_matches(
            args.offset, sport, all_leagues=args.all_leagues
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[-] матчи дня недоступны: {exc}")
        return 1

    print(f"[*] К анализу: {len(kept)}")
    if not kept:
        print("[!] На этот день матчей нет (или все отсеяны фильтром)")
        if not args.all_leagues:
            print("    Попробуйте --all-leagues (все лиги дня)")
        return 0

    if args.list_only:
        for m in kept:
            print(
                f"    {str(m.get('date_match') or ''):16} "
                f"{str(m.get('tour_name') or ''):28} "
                f"{m.get('home_name', '')} - {m.get('away_name', '')}"
            )
        return 0

    from analyze_match import _coerce_strategies, run_analyze
    from match_store import upsert_matches

    written = upsert_matches(kept, sport, leagues=cfg.leagues_for_sport(sport))
    print(f"[+] В очередь записано: {written}")

    ids = [m["match_id"] for m in kept if m.get("match_id")]
    return run_analyze(
        match_ids=ids,
        only_strategies=_coerce_strategies(args.strategies),
        fail_fast=not args.no_fail_fast,
    )


if __name__ == "__main__":
    sys.exit(main())
