"""CLI: анализ матчей из БД-очереди → Python-calc → matches.db."""

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
from db import create_database, get_db_connection  # noqa: E402


def _match_analyzed(match_id: str) -> bool:
    """True, если матч уже проанализирован (есть прогноз в matches)."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT prediction FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    if not row:
        return False
    pred = (row["prediction"] if hasattr(row, "keys") else row[0]) or ""
    return str(pred).strip() not in ("", "-")


# Таблицы с колонкой match_id, которые сбрасываются флагом --reset.
# Сюда НЕ входят:
#   teams / leagues / countries  — справочники, общие для всех матчей;
#   match_queue                  — очередь, откуда берутся матчи;
#   team_matches_cache           — история команд (общий кэш, не результат матча);
#   *_rating_history             — пересчитывается отдельно (ratings.py);
#   match_snapshot               — это ВХОДНЫЕ данные (таблица, форма, H2H, матчи
#                                  команд), а не результат. Удалять его нельзя:
#                                  при повторном анализе таблица не загрузится
#                                  (страница лиги может быть недоступна), и прогноз
#                                  потеряется. Снимок обновляется сам при анализе;
#   match_weather                — тоже входные данные (погода на матч);
#   match_stats                  — статистика матча из фида, не наш расчёт.
RESET_TABLES = (
    "strategy_predictions",
    "odds",
    "outcome_probabilities",
    "goal_probabilities",
    "match_missing_players",
    "moneyway",
    "whoscored_preview",
    "ml_predictions",
    "odds_history",
    "odds_backup",
)

# В matches сбрасываем поля результата анализа, но оставляем идентификацию
# (league_id, home_team_id, away_team_id, sport, start_ts, match_date, счёт).
RESET_MATCH_COLUMNS = (
    "prediction = NULL",
    "match_status = NULL",
)


def reset_matches(match_ids: list[str], *, dry_run: bool = False) -> dict[str, int]:
    """Удалить результаты прошлого анализа, чтобы прогнать матчи заново.

    Возвращает {таблица: удалено_строк}; таблицы без match_id пропускаются.
    """
    ids = [m for m in (match_ids or []) if m]
    if not ids:
        return {}

    counts: dict[str, int] = {}
    placeholders = ",".join("?" for _ in ids)
    with get_db_connection() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in RESET_TABLES:
            if table not in existing:
                continue
            cols = {
                r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            if "match_id" not in cols:
                continue
            if dry_run:
                n = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE match_id IN ({placeholders})',
                    ids,
                ).fetchone()[0]
            else:
                cur = conn.execute(
                    f'DELETE FROM "{table}" WHERE match_id IN ({placeholders})',
                    ids,
                )
                n = cur.rowcount or 0
            counts[table] = n

        if dry_run:
            n = conn.execute(
                f"SELECT COUNT(*) FROM matches WHERE match_id IN ({placeholders}) "
                "AND prediction IS NOT NULL AND TRIM(prediction) <> ''",
                ids,
            ).fetchone()[0]
        else:
            sets = ", ".join(RESET_MATCH_COLUMNS)
            cur = conn.execute(
                f"UPDATE matches SET {sets} WHERE match_id IN ({placeholders})",
                ids,
            )
            n = cur.rowcount or 0
        counts["matches"] = n
        if not dry_run:
            conn.commit()
    return counts


STRATEGY_IDS = {
    1: "calc/NTB", 2: "calc/Betalone", 3: "calc/Sniper",
    4: "BTS", 5: "Favorites", 6: "StavkaTV",
    7: "Moneyway/dogs", 8: "1pr", 9: "WhoScored", 10: "XGBoost",
}


def _coerce_strategies(value) -> set | None:
    """'all'/'1,2,3'/None → set[int] или None (все)."""
    if value in (None, "", "all"):
        return None
    if isinstance(value, set):
        return value
    if isinstance(value, int):
        return {value}
    ids = set()
    for part in str(value).replace(";", ",").split(","):
        part = part.strip().lstrip("#")
        if part.isdigit():
            ids.add(int(part))
    return ids or None


def _season_alert(kind: str = "error", *, times: int = 1) -> None:
    """Звуковой сигнал при остановке анализа сезона.

    kind: 'error' — ошибка/прерывание (тревожный нисходящий тон).
    Не блокирует: звук играет в фоновом потоке.
    """
    try:
        from sound_alert import alert_error_async

        alert_error_async(times=times)
    except Exception:  # noqa: BLE001
        pass


def run_analyze_season(
    *,
    workbook: str = "",
    season_url: str = "",
    limit: int = 0,
    only_strategies=None,
    fail_fast: bool = True,
    skip_analyzed: bool = True,
    reset: bool = False,
) -> int:
    """Анализ всех матчей сезона по ссылке.

    - Кэш матчей команд: история читается из архивных `matches` (is_archived=1),
      недостающее догружается pr_ фидом и сохраняется в кэш.
    - skip_analyzed=True: уже проанализированные матчи пропускаются.
      skip_analyzed=False: проходим все матчи (режим дополнения стратегий).
    - reset=True: перед анализом удалить результаты прошлого прогона для этих
      матчей (прогнозы стратегий, кф, вероятности, снимок, погода, статистика)
      и обнулить прогноз/статус в `matches` — анализ начинается заново.
      Справочники (команды, лиги) и кэш истории команд не трогаются.
    - fail_fast: при ошибке матча — прерывание (continue с места остановки).
    """
    from tournament_resolver import resolve_season_from_url
    from archive_old_match import fetch_tournament_matches
    from team_history import format_match_date

    cfg = DeluxSettings.from_env()
    calc_workbook = workbook or ""
    create_database()

    strat_set = _coerce_strategies(only_strategies)
    strat_label = "все" if strat_set is None else ", ".join(STRATEGY_IDS.get(i, str(i)) for i in sorted(strat_set))

    meta = resolve_season_from_url(season_url)
    if not meta.get("season_id") or not meta.get("tournament_key"):
        print(f"[-] Не удалось резолвить сезон из URL: {season_url}")
        _season_alert("resolve")
        return 1

    sport = int(meta["sport"])
    country_id = int(meta["country_id"] or 198)
    tournament_key = meta["tournament_key"]
    season_id = meta["season_id"]

    print(f"[*] Сезон: sport={sport} country_id={country_id} "
          f"tournament_key={tournament_key} season_id={season_id} | стратегии: {strat_label}")

    all_matches = fetch_tournament_matches(sport, country_id, tournament_key, season_id)
    if not all_matches:
        print("[-] Не удалось загрузить матчи турнира")
        _season_alert("no_matches")
        return 1

    print(f"[*] Матчей в сезоне: {len(all_matches)}")

    if limit > 0:
        all_matches = all_matches[:limit]

    # --reset: стираем результаты прошлого прогона, чтобы считать заново.
    if reset:
        print("[*] --reset: сбрасываю результаты прошлого анализа")
        counts = reset_matches([tm["match_id"] for tm in all_matches])
        for table, n in counts.items():
            if n:
                print(f"    {table}: удалено {n}")
        print("[*] Пересчёт всех матчей сезона: "
              f"{len(all_matches)} (пропуск ранее готовых отключён)")

    # Отсев уже проанализированных
    todo = []
    skipped_done = 0
    if skip_analyzed and not reset:
        for tm in all_matches:
            if _match_analyzed(tm["match_id"]):
                skipped_done += 1
            else:
                todo.append(tm)
    else:
        todo = list(all_matches)
    if skipped_done:
        print(f"[*] Уже проанализировано (пропущено): {skipped_done}")
    print(f"[*] К анализу: {len(todo)}")

    arbworld_index = None
    whoscored_index = None
    if sport == 1:
        if strat_set is None or 7 in strat_set:
            try:
                from dogs_strategy import get_arbworld_index
                arbworld_index = get_arbworld_index()
            except Exception as exc:
                print(f"[!] Arbworld: {exc}")
        if strat_set is None or 9 in strat_set:
            try:
                from whoscored_strategy import load_whoscored_index
                whoscored_index = load_whoscored_index(cfg.leagues_for_sport(1))
            except Exception as exc:
                print(f"[!] WhoScored: {exc}")

    ok = 0
    failed = 0
    with get_calc_engine(cfg) as engine:
        for idx, tm in enumerate(todo, 1):
            mid = tm["match_id"]
            home = tm["home_name"]
            away = tm["away_name"]
            league = tm["competition"]
            print(f"\n[{idx}/{len(todo)}] {mid} | {league} | {home} - {away}")

            queued = QueuedMatch(
                match_id=mid,
                sport=sport,
                home_name=home,
                away_name=away,
                tour_name=league,
            )
            queued.start_ts = tm.get("kickoff_ts") or 0
            queued.score_home = tm.get("home_score")
            queued.score_away = tm.get("away_score")
            queued.date_match = format_match_date(tm.get("kickoff_ts") or 0)
            queued.country_id = str(country_id)
            match = queued.to_match_info()

            from analysis_data import build_settings
            ms = build_settings(
                sport=sport,
                source=cfg.source,
                tz_base=cfg.tz_base,
                dayzone_base=cfg.dayzone_base,
                time_offset=cfg.time_offset,
            )

            try:
                analyze_match(
                    calc_workbook,
                    match,
                    ms,
                    queued=queued,
                    engine=engine,
                    arbworld_index=arbworld_index,
                    whoscored_index=whoscored_index,
                    only_strategies=strat_set,
                )
                ok += 1
                print(f"[+] Сохранено в БД: {mid}")
            except Exception as exc:
                failed += 1
                print(f"[-] Ошибка {mid}: {exc}")
                if fail_fast:
                    print(f"[!] Прерывание на матче {mid} (прогресс сохранён). "
                          f"Повторный запуск продолжит с этого места.")
                    # Звук: прогон остановлен, нужно вмешательство.
                    _season_alert("fail_fast")
                    break

    # Сигнал, если что-то пошло не так даже при --no-fail-fast.
    if failed and not fail_fast:
        _season_alert("errors", times=1)

    print(f"\n[+] Готово: ok={ok}, ошибок={failed}, пропущено ранее={skipped_done}")
    return 0 if failed == 0 else 1


def run_analyze(
    *,
    workbook: str = "",
    match_id: str = "",
    match_ids: Optional[list[str]] = None,
    new: bool = False,
    all_matches: bool = False,
    limit: int = 0,
    only_strategies=None,
    fail_fast: bool = True,
) -> int:
    cfg = DeluxSettings.from_env()
    calc_workbook = workbook or ""
    create_database()

    strat_set = _coerce_strategies(only_strategies)

    if match_ids:
        # Явный список (например матчи одного дня): берём всё, что есть в очереди.
        wanted = [m for m in match_ids if m]
        by_id = {q.match_id: q for q in list_queued_matches()}
        matches = []
        for mid in wanted:
            queued = by_id.get(mid) or get_queued_match(mid)
            matches.append(queued or QueuedMatch(match_id=mid, sport=cfg.sport))
        if limit > 0:
            matches = matches[:limit]
        print(f"[*] Явный список: {len(matches)} матчей")
    elif match_id:
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

    whoscored_index = None
    if any(int(q.sport or 1) == 1 for q in matches):
        try:
            from whoscored_strategy import last_whoscored_error, load_whoscored_index

            leagues = cfg.leagues_for_sport(1)
            print("[*] WhoScored (#9): fetching previews for favorite leagues")
            whoscored_index = load_whoscored_index(leagues)
            if whoscored_index is not None:
                print(f"[*] WhoScored (#9): previews={len(whoscored_index)}")
            else:
                print(f"[!] WhoScored (#9): skip — {last_whoscored_error() or 'unknown'}")
        except Exception as exc:
            print(f"[!] WhoScored (#9): fetch failed — {exc}")

    print("[*] Strategies on analyze: #1-3 calc, #4 BTS, #5 Favorites, #6 StavkaTV, #7 Moneyway, #8 1pr, #9 WhoScored, #10 XGBoost")

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
                results = analyze_match(
                    calc_workbook,
                    match,
                    ms,
                    queued=queued,
                    engine=engine,
                    arbworld_index=arbworld_index,
                    whoscored_index=whoscored_index,
                    only_strategies=strat_set,
                )
                ok += 1
                print(f"[+] Сохранено в БД: {match.match_id}")
                # Вывод прогнозов с коэффициентами
                pred_ntb = results.get("prediction_ntb") or ""
                pred_sniper = results.get("prediction_sniper") or ""
                pred_betalone = results.get("prediction_betalone") or ""
                odds_ntb = results.get("odds_ntb")
                odds_sniper = results.get("odds_sniper")
                odds_betalone = results.get("odds_betalone")
                if pred_ntb:
                    odds_str = f" @ {odds_ntb:.2f}" if odds_ntb else ""
                    print(f"    NTB: {pred_ntb}{odds_str}")
                if pred_sniper:
                    odds_str = f" @ {odds_sniper:.2f}" if odds_sniper else ""
                    print(f"    Sniper: {pred_sniper}{odds_str}")
                if pred_betalone:
                    odds_str = f" @ {odds_betalone:.2f}" if odds_betalone else ""
                    print(f"    Betalone: {pred_betalone}{odds_str}")
            except Exception as exc:
                print(f"[-] Ошибка {match.match_id}: {exc}")
                if fail_fast:
                    _season_alert("fail_fast")
                    break

    print(f"\n[+] Готово: {ok}/{len(matches)}")
    return 0 if ok else 1


def _interactive_menu() -> int:
    """Интерактивный выбор: режим анализа + стратегии + ссылка на сезон."""
    print("=" * 55)
    print("  Анализ матчей DeluX")
    print("=" * 55)
    print("  1) Все матчи (очередь)        2) Один сезон (по ссылке)")
    print("  3) Один матч (по ID)")
    print("  4) Дополнить стратегиями (сезон/матч, только выбранные)")
    print("  5) Сезон заново (--reset: стереть прошлые прогнозы)")
    print("=" * 55)

    mode = input("Режим [1/2/3/4/5]: ").strip()
    if mode == "1":
        strategies = _ask_strategies()
        return run_analyze(new=True, all_matches=False, only_strategies=strategies)
    if mode == "2":
        season_url = input("Ссылка на сезон: ").strip()
        if not season_url:
            print("[-] Ссылка не введена")
            return 1
        strategies = _ask_strategies()
        return run_analyze_season(season_url=season_url, only_strategies=strategies)
    if mode == "5":
        season_url = input("Ссылка на сезон: ").strip()
        if not season_url:
            print("[-] Ссылка не введена")
            return 1
        strategies = _ask_strategies()
        print("[!] Будут удалены прогнозы, кф и вероятности ВСЕХ матчей этого сезона.")
        confirm = input("Продолжить? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes", "д", "да"):
            print("[-] Отменено")
            return 1
        return run_analyze_season(
            season_url=season_url,
            only_strategies=strategies,
            reset=True,
        )
    if mode == "3":
        match_id = input("ID матча: ").strip()
        if not match_id:
            print("[-] ID не введён")
            return 1
        strategies = _ask_strategies()
        return run_analyze(match_id=match_id, only_strategies=strategies)
    if mode == "4":
        return _update_menu()
    print("[-] Неверный выбор")
    return 1


def _update_menu() -> int:
    """Режим дополнения: пройти по уже готовым матчам и добавить выбранные стратегии."""
    print("-" * 55)
    print("  Дополнение стратегиями (данные уже есть)")
    print("  a) Дополнить все матчи сезона   b) Дополнить один матч")
    print("-" * 55)
    sub = input("Вариант [a/b]: ").strip().lower()
    strategies = _ask_strategies()
    if not strategies:
        print("[-] Для дополнения нужно указать конкретные стратегии (не 'all')")
        return 1
    if sub == "a":
        season_url = input("Ссылка на сезон: ").strip()
        if not season_url:
            print("[-] Ссылка не введена")
            return 1
        return run_analyze_season(
            season_url=season_url,
            only_strategies=strategies,
            skip_analyzed=False,
        )
    if sub == "b":
        match_id = input("ID матча: ").strip()
        if not match_id:
            print("[-] ID не введён")
            return 1
        return run_analyze(match_id=match_id, only_strategies=strategies)
    print("[-] Неверный выбор")
    return 1


def _ask_strategies():
    """Выбор стратегий: 'all' или номера через запятую. Возвращает set|None."""
    print("-" * 55)
    for sid in sorted(STRATEGY_IDS):
        print(f"  #{sid}: {STRATEGY_IDS[sid]}")
    print("-" * 55)
    ans = input("Стратегии [all или номера через запятую, напр. 1,3,9]: ").strip()
    return _coerce_strategies(ans)


def main():
    parser = argparse.ArgumentParser(description="Python-анализ DeluX")
    parser.add_argument("--workbook", default="")
    parser.add_argument("--season-url", default="", help="Ссылка на сезон (напр. .../premier-league-2015-2016/)")
    parser.add_argument("--limit", type=int, default=0, help="Ограничить число матчей (для season-url)")
    parser.add_argument("--strategies", default="", help="Стратегии: all или номера через запятую (1..10)")
    parser.add_argument("--no-fail-fast", action="store_true", help="Не прерываться при ошибке")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Начать анализ сезона заново: удалить прошлые прогнозы, кф и вероятности",
    )
    parser.add_argument("--interactive", action="store_true", help="Интерактивное меню выбора")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--match-id")
    group.add_argument("--new", action="store_true")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.interactive:
        raise SystemExit(_interactive_menu())

    strategies = _coerce_strategies(args.strategies)

    if args.season_url:
        raise SystemExit(
            run_analyze_season(
                workbook=args.workbook,
                season_url=args.season_url,
                limit=args.limit,
                only_strategies=strategies,
                fail_fast=not args.no_fail_fast,
                reset=args.reset,
            )
        )

    if not args.match_id and not args.new and not args.all:
        # нет аргументов → интерактивное меню
        raise SystemExit(_interactive_menu())
    raise SystemExit(
        run_analyze(
            workbook=args.workbook,
            match_id=args.match_id or "",
            new=args.new,
            all_matches=args.all,
            only_strategies=strategies,
        )
    )


if __name__ == "__main__":
    main()
