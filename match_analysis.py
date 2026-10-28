"""Анализ матча: данные из API → Python-calc → сохранение в БД."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from analysis_data import AnalysisPayload, MatchInfo, MatchSettings, build_settings, load_analysis_data
from bts_strategy import BTS_STRATEGY_ID, compute_bts_prediction
from dogs_strategy import DOGS_STRATEGY_ID, build_moneyway_snapshot
from favorites_strategy import FAVORITES_STRATEGY_ID, compute_favorites_win_prediction
from stavka_tv_strategy import STAVKA_TV_STRATEGY_ID, compute_stavka_tv_prediction
from whoscored_strategy import WHOSCORED_STRATEGY_ID, compute_whoscored_prediction
from src.strategies.xgboost import XGBoostStrategy, MatchContext
from favorites_stats.injuries import fetch_and_store_for_match
from calc_backend import CalcEngine, get_calc_engine
from db import (
    create_database,
    calculate_and_save_venue_distance,
    get_db_connection,
    get_service_team_name,
    get_team_venue_id,
    insert_goal_probabilities_from_values,
    insert_or_get_country,
    insert_or_get_league,
    insert_or_get_team,
    insert_outcome_probabilities_from_values,
    parse_league,
    upsert_moneyway,
)
from match_stats import fetch_match_stats, save_match_stats
from team_stats_5matches import (
    analyze_team_form,
    save_team_stats_to_db,
)
from match_snapshot import (
    describe_match_info,
    describe_payload_snapshot,
    save_match_info,
    save_payload_snapshot,
)
from match_store import QueuedMatch
from weather import describe_weather, save_weather_snapshot
from odds_service import build_fallback_odds, load_odds
from prediction_odds import fill_prediction_odds, odds_lookup, resolve_prediction_odds
from settings import DeluxSettings, queue_sport_id
from date_utils import normalize_match_date
from flashscore_feed import FLASHSCORE_SOURCER


def _fetch_match_status(match_id: str, sport: int) -> Optional[int]:
    """Определяет статус матча: сначала из БД, потом из dc_ фида.
    
    Статусы:
        0 — не начался
        1 — live
        2 — завершён (первый тайм)
        3 — завершён (полный матч)
    """
    from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed, FLASHSCORE_SOURCER
    
    # 1) Сначала проверяем БД
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT match_status, score_home, score_away FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        
        if row:
            status_str = row["match_status"] or ""
            score_h = row["score_home"]
            score_a = row["score_away"]
            
            # Если есть оба счёта — матч завершён (даже если статус неверный)
            if score_h is not None and score_a is not None:
                print(f"    Статус матча: 3 (из БД - есть счёт {score_h}:{score_a})")
                return 3
            
            if status_str == "Завершен":
                print(f"    Статус матча: 3 (из БД - Завершен)")
                return 3
            elif status_str == "Live":
                print(f"    Статус матча: 1 (из БД - Live)")
                return 1
            elif status_str == "Не начался":
                print(f"    Статус матча: 0 (из БД - Не начался)")
                return 0
    
    # 2) Если в БД нет — пробуем dc_ feed
    url = f"https://{FLASHSCORE_SOURCER}x/feed/dc_{int(sport)}_{match_id}"
    try:
        text = fetch_feed(url)
    except Exception as exc:
        print(f"    [!] dc_ feed error: {exc}")
        return None
    
    if not text:
        print(f"    [!] dc_ feed пустой для {match_id}")
        return None
    
    for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
        key, sep, value = chunk.partition(FIELD_SEP)
        if sep and key.strip() in ("AR", "DA"):
            try:
                status = int(float(value.strip()))
                print(f"    [DEBUG] dc_ {key.strip()}={status} для {match_id}")
                return status
            except (ValueError, TypeError):
                pass
    
    print(f"    [!] AR/DA не найден в dc_ для {match_id}, длина текста={len(text)}")
    return None


def _fetch_match_score(match_id: str, sport: int) -> Tuple[Optional[int], Optional[int]]:
    """Итоговый счёт матча из dc_ фида (поля DE/DF)."""
    from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed, FLASHSCORE_SOURCER
    url = f"https://{FLASHSCORE_SOURCER}x/feed/dc_{int(sport)}_{match_id}"
    try:
        text = fetch_feed(url, retries=2, timeout=30)
    except Exception as exc:
        print(f"    [!] dc_ для счёта: {exc}")
        return None, None
    if not text:
        return None, None

    score_home = score_away = None
    for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
        key, sep, value = chunk.partition(FIELD_SEP)
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key == "DE":
            try:
                score_home = int(float(value))
            except (ValueError, TypeError):
                pass
        elif key == "DF":
            try:
                score_away = int(float(value))
            except (ValueError, TypeError):
                pass
    return score_home, score_away


_SERVICE_LABELS = {
    "arbworld": "Arbworld / dogs",
    "whoscored": "WhoScored",
}


def _ensure_service_aliases(
    home: str,
    away: str,
    service: str,
    *,
    interactive: Optional[bool] = None,
) -> List[str]:
    """Проверить и при необходимости запросить имена команд для сервиса.

    Возвращает список Flashscore-имён команд, у которых НЕТ alias в БД
    (т.е. стратегия по ним не сможет точно определить команду).

    interactive: True/False принудительно; None — автоопределение по
    sys.stdin.isatty() (в пайплайне/фоне не спрашиваем).
    """
    import sys
    from db import get_service_team_name, set_service_team_name

    label = _SERVICE_LABELS.get(service, service)
    if interactive is None:
        interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())

    missing: List[str] = []
    # Сначала собираем список недостающих — чтобы один раз пикнуть на весь
    # список, а не по сигналу на каждую команду.
    pending: List[str] = []
    for fs_name in (home, away):
        fs_name = (fs_name or "").strip()
        if not fs_name:
            continue
        if get_service_team_name(fs_name, service):
            continue
        pending.append(fs_name)

    if pending and interactive:
        # Звук привлекает внимание: анализ сезона ждёт ввода и «висит».
        try:
            from sound_alert import alert_attention_async

            alert_attention_async(times=len(pending))
        except Exception:  # noqa: BLE001
            pass

    for fs_name in pending:
        # Нет alias → команда не разрешится точно в сервисе.
        missing.append(fs_name)
        if not interactive:
            continue
        try:
            answer = input(
                f"\n  [{label}] Имя команды '{fs_name}' не задано для {label}.\n"
                f"  Введите имя в {label} (или Enter — пропустить): "
            ).strip()
        except (EOFError, KeyboardInterrupt, OSError, ValueError):
            continue
        if answer:
            set_service_team_name(fs_name, service, answer)
            print(f"    [OK] {label}: '{fs_name}' -> '{answer}' (сохранено)")

    return missing


def _cached_team_matches(
    team_name: str,
    kickoff_ts: int,
    *,
    home_key: str,
    country: int,
    sport: int,
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Матчи команды до целевого: сначала из кэша `team_matches_cache`,
    недостающее догружаем pr_ фидом и сохраняем в кэш.

    Возвращает хронологический список. НЕ трогает таблицу `matches`.
    """
    from team_history import (
        get_team_archived_matches,
        fetch_team_matches_before,
        save_team_matches_cache,
    )

    name = (team_name or "").strip()
    cached = get_team_archived_matches(name, before_ts=kickoff_ts, limit=limit)
    if len(cached) >= limit:
        return cached

    # Догрузка из сети
    fetched: List[Dict[str, Any]] = []
    if home_key:
        try:
            fetched = fetch_team_matches_before(
                home_key, kickoff_ts, country=country, sport=sport, limit=limit
            )
            # сохраняем догруженное в кэш (не в matches)
            if fetched:
                try:
                    save_team_matches_cache(home_key, name, fetched)
                except Exception as exc:  # noqa: BLE001
                    print(f"    [!] запись кэша команды {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] pr_ fetch для {name}: {exc}")

    # Сливаем: кэш + сеть (dedup по match_id), сортируем, берём последние limit
    merged: Dict[str, Dict[str, Any]] = {}
    for m in cached:
        merged.setdefault(m["match_id"], m)
    for m in fetched:
        merged.setdefault(m["match_id"], m)
    ordered = sorted(merged.values(), key=lambda m: (m["kickoff_ts"], m["match_id"]))
    return ordered[-limit:]


def save_analysis_to_db(
    match_id: str,
    sport: int,
    results: Dict[str, Any],
    odds_markets: Optional[list] = None,
    *,
    partial: bool = False,
) -> bool:
    league_str = str(results.get("league") or "")
    country_name, league_name = parse_league(league_str)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        country_id = insert_or_get_country(cursor, country_name)
        league_id = insert_or_get_league(cursor, league_name, country_id)
        home_team_id = insert_or_get_team(cursor, str(results.get("home") or ""))
        away_team_id = insert_or_get_team(cursor, str(results.get("away") or ""))

        prediction = str(results.get("prediction_ntb") or results.get("prediction_sniper") or "")

        # partial (дополнение доп. стратегией): не затираем главный prediction,
        # если calc не считался — сохраняем прежнее значение.
        if partial and not prediction:
            existing_pred = cursor.execute(
                "SELECT prediction FROM matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()
            if existing_pred:
                prediction = (existing_pred["prediction"] if hasattr(existing_pred, "keys") else existing_pred[0]) or ""

        existing = cursor.execute(
            "SELECT start_ts, score_home, score_away, match_status FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        start_ts = results.get("start_ts")
        if start_ts is None and existing:
            start_ts = existing["start_ts"]

        # Дата/start_ts должны быть заполнены: без них «последние матчи»
        # (team_form_stats) читаются с пустой датой, а фильтр по start_ts
        # отбрасывает матч. Берём из dc_ фида, если расчёт их не дал.
        match_date = normalize_match_date(results.get("match_date") or "")
        if not match_date or start_ts is None:
            try:
                from feed_ids import match_start_ts

                ts_from_feed = match_start_ts(match_id, sport=sport)
            except Exception:  # noqa: BLE001
                ts_from_feed = 0
            if ts_from_feed:
                if start_ts is None:
                    start_ts = ts_from_feed
                if not match_date:
                    from team_history import format_match_date

                    match_date = format_match_date(ts_from_feed)

        # Счёт и статус: берём из results, иначе сохраняем уже имеющиеся в БД.
        score_home = results.get("score_home")
        score_away = results.get("score_away")
        match_status = results.get("match_status")
        if score_home is None and existing:
            score_home = existing["score_home"]
        if score_away is None and existing:
            score_away = existing["score_away"]
        if match_status is None and existing:
            match_status = existing["match_status"]

        cursor.execute(
            """
            INSERT OR REPLACE INTO matches
            (match_id, match_date, start_ts, league_id, home_team_id, away_team_id,
             prediction, sport, score_home, score_away, match_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                match_date,
                start_ts,
                league_id,
                home_team_id,
                away_team_id,
                prediction,
                sport,
                score_home,
                score_away,
                match_status,
            ),
        )

        strategy_predictions = {
            1: str(results.get("prediction_ntb") or ""),
            2: str(results.get("prediction_betalone") or ""),
            3: str(results.get("prediction_sniper") or ""),
        }
        for strategy_id, pred in strategy_predictions.items():
            if pred.strip():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO strategy_predictions (match_id, strategy_id, prediction)
                    VALUES (?, ?, ?)
                    """,
                    (match_id, strategy_id, pred.strip()),
                )

        bts_pred = str(results.get("prediction_bts") or "").strip()
        if bts_pred:
            cursor.execute(
                """
                INSERT OR REPLACE INTO strategy_predictions
                (match_id, strategy_id, prediction, odds, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    BTS_STRATEGY_ID,
                    bts_pred,
                    results.get("bts_odds"),
                    results.get("bts_notes"),
                ),
            )

        fav_pred = str(results.get("prediction_favorites") or "").strip()
        if fav_pred:
            cursor.execute(
                """
                INSERT OR REPLACE INTO strategy_predictions
                (match_id, strategy_id, prediction, odds, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    FAVORITES_STRATEGY_ID,
                    fav_pred,
                    results.get("favorites_odds"),
                    results.get("favorites_notes"),
                ),
            )

        for key, sid in (
            ("stavka", STAVKA_TV_STRATEGY_ID),
            ("dogs", DOGS_STRATEGY_ID),
            ("whoscored", WHOSCORED_STRATEGY_ID),
            ("xgboost", 10),
        ):
            pred = str(results.get(f"prediction_{key}") or "").strip()
            if pred:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO strategy_predictions
                    (match_id, strategy_id, prediction, odds, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        sid,
                        pred,
                        results.get(f"{key}_odds"),
                        results.get(f"{key}_notes"),
                    ),
                )

        if odds_markets:
            cursor.execute("DELETE FROM odds WHERE match_id = ?", (match_id,))
            from odds_normalize import canonicalize_market, split_canonical

            batch = []
            for m in odds_markets:
                canon = canonicalize_market(
                    m.get("market_name"),
                    outcome=m.get("outcome"),
                    side=m.get("side"),
                    line_value=m.get("line_value"),
                )
                if not canon:
                    continue
                meta = split_canonical(canon)
                batch.append(
                    (
                        match_id,
                        canon,
                        meta.get("outcome") or m.get("outcome"),
                        meta.get("side") or m.get("side"),
                        meta.get("line_value")
                        if meta.get("line_value") is not None
                        else m.get("line_value"),
                        m["odds_value"],
                    )
                )
            cursor.executemany(
                """
                INSERT INTO odds (match_id, market_name, outcome, side, line_value, odds_value)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                batch,
            )

        # Кф в прогнозы стратегий: 'ТБ 1,5' → OVER 1.5 и т.п.
        try:
            filled = fill_prediction_odds(conn, match_id)
            for _mid, sid, pred, val in filled:
                print(f"    Кф #{sid}: {pred} @ {val:g}")
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] проставление кф: {exc}")

    insert_outcome_probabilities_from_values(match_id, results.get("outcome_probabilities") or [])
    insert_goal_probabilities_from_values(match_id, results.get("home_goals") or [], results.get("away_goals") or [])

    moneyway_snap = results.get("moneyway")
    if isinstance(moneyway_snap, dict):
        try:
            upsert_moneyway(match_id, moneyway_snap)
        except Exception as exc:
            print(f"[moneyway] save failed: {exc}")

    try:
        from db import should_skip_onepr
        from onepr_hook import sync_1pr_signal

        if not should_skip_onepr():
            sync_1pr_signal(match_id)
    except Exception as exc:
        print(f"[1pr] hook failed: {exc}")

    # Рейтинги Glicko-2 / OpenSkill: обновляются только для завершённых матчей
    # (внутри проверяется is_finished_status). Без этого хука рейтинги оставались
    # на дефолтных значениях, т.к. update_* вызывались лишь из CLI.
    _update_ratings(match_id)

    # Завершённый матч — сразу считаем результат и прибыль прогнозов.
    if match_status == 3:
        settle_match_predictions(match_id)
    return True


def settle_match_predictions(match_id: str) -> Optional[Dict[str, Any]]:
    """Посчитать result/profit по уже сохранённым прогнозам завершённого матча.

    Пишет результат в strategy_predictions (result, profit) и суммарную прибыль
    в matches.profit. Возвращает {'total': ..., 'rows': [...]} или None.
    """
    from match_settle import is_finished_status, settle_prediction_row

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT match_id, match_status, score_home, score_away "
            "FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if not row:
            return None
        status = row["match_status"]
        score_home = row["score_home"]
        score_away = row["score_away"]
        if not is_finished_status(status, score_home, score_away):
            return None

        total_home = int(score_home)
        total_away = int(score_away)
        result_1x2 = (
            "П1" if total_home > total_away
            else ("П2" if total_home < total_away else "X")
        )

        preds = conn.execute(
            "SELECT id, strategy_id, prediction, odds, notes, stake "
            "FROM strategy_predictions WHERE match_id = ?",
            (match_id,),
        ).fetchall()

        total_profit = 0.0
        settled: List[Dict[str, Any]] = []
        for p in preds:
            pred = (p["prediction"] or "").strip()
            if not pred or pred in ("-", "0"):
                conn.execute(
                    "UPDATE strategy_predictions SET result = ?, profit = 0 "
                    "WHERE id = ?",
                    ("Нет прогноза", p["id"]),
                )
                continue
            odds = float(p["odds"] or 0) or 0.0
            # Без коэффициента прибыль не посчитать — фиксируем только результат.
            coeff = odds if odds > 1 else 1.0
            stake = float(p["stake"] or 1.0)
            status_text, profit = settle_prediction_row(
                pred,
                result_1x2,
                total_home,
                total_away,
                coeff,
                notes=p["notes"],
                stake=stake,
            )
            if odds <= 1:
                # Кф нет: результат известен, деньги не считаем.
                profit = 0.0
                status_text = f"{status_text} (нет кф)"
            conn.execute(
                "UPDATE strategy_predictions SET result = ?, profit = ? WHERE id = ?",
                (status_text, profit, p["id"]),
            )
            total_profit += float(profit)
            settled.append(
                {
                    "strategy_id": p["strategy_id"],
                    "prediction": pred,
                    "odds": p["odds"],
                    "result": status_text,
                    "profit": profit,
                }
            )

        conn.execute(
            "UPDATE matches SET profit = ? WHERE match_id = ?",
            (round(total_profit, 4), match_id),
        )
        conn.commit()

    print(f"    Итог: {total_home}:{total_away} ({result_1x2})")
    for s in settled:
        print(
            f"      #{s['strategy_id']} {s['prediction']} @ {s['odds']} "
            f"-> {s['result']} ({s['profit']:+.2f})"
        )
    print(f"    Прибыль: {total_profit:+.2f}")
    return {"total": total_profit, "rows": settled}


def _update_ratings(match_id: str) -> None:
    """Обновить Glicko-2 и OpenSkill по завершённому матчу (тихо при ошибках)."""
    try:
        import ratings
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] рейтинги: модуль ratings недоступен ({exc})")
        return

    try:
        res = ratings.update_glicko2_for_match(match_id)
        if res:
            before = res.get("glicko2_before") or {}
            after = res.get("glicko2_after") or {}
            print(
                f"    Glicko-2: {before.get('home')} -> {after.get('home')} / "
                f"{before.get('away')} -> {after.get('away')}"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] Glicko-2: {exc}")

    try:
        res = ratings.update_openskill_for_match(match_id)
        if res:
            home = res.get("home") or {}
            away = res.get("away") or {}
            print(f"    OpenSkill: {home.get('mu')} / {away.get('mu')} (mu)")
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] OpenSkill: {exc}")

    # ELO обновляется в том же месте: раньше это делал только result_checker,
    # поэтому при анализе матча рейтинг ELO оставался нетронутым.
    try:
        import elo

        res = elo.update_elo_for_match(match_id)
        if res:
            before = res.get("elo_before") or {}
            after = res.get("elo_after") or {}
            delta = res.get("delta") or {}
            print(
                f"    ELO: {before.get('home')} -> {after.get('home')} "
                f"({delta.get('home'):+.1f}) / {before.get('away')} -> {after.get('away')} "
                f"({delta.get('away'):+.1f})"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] ELO: {exc}")


def _list_odds_from_queue(queued: Optional[QueuedMatch]) -> Optional[Tuple[float, float, float]]:
    if not queued:
        return None
    if queued.current_home or queued.current_draw or queued.current_away:
        return queued.current_home, queued.current_draw, queued.current_away
    if queued.start_home or queued.start_draw or queued.start_away:
        return queued.start_home, queued.start_draw, queued.start_away
    return None


def analyze_match(
    calc_workbook: str,
    match: MatchInfo,
    settings: Optional[MatchSettings] = None,
    *,
    save_to_db: bool = True,
    queued: Optional[QueuedMatch] = None,
    engine: Optional[CalcEngine] = None,
    arbworld_index: Optional[dict] = None,
    whoscored_index: Optional[list] = None,
    only_strategies: Optional[set] = None,
) -> Dict[str, Any]:
    settings = settings or build_settings()

    def strat_on(strategy_id: int) -> bool:
        """Проверить, нужно ли считать стратегию (None = все)."""
        return only_strategies is None or strategy_id in only_strategies
    
    # Передаём start_ts из queued или из БД в match
    if queued and queued.start_ts:
        match.start_ts = queued.start_ts
        print(f"    [DEBUG] start_ts из queued: {match.start_ts}")
    elif not match.start_ts:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT start_ts FROM matches WHERE match_id = ?",
                (match.match_id,),
            ).fetchone()
            if row and row["start_ts"]:
                match.start_ts = row["start_ts"]
                print(f"    [DEBUG] start_ts из БД: {match.start_ts}")
            else:
                print(f"    [DEBUG] start_ts пустой для {match.match_id}, пытаемся dc_ feed...")
                # Попробуем загрузить из dc_ фида
                from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed, FLASHSCORE_SOURCER
                url = f"https://{FLASHSCORE_SOURCER}x/feed/dc_{settings.sport}_{match.match_id}"
                try:
                    text = fetch_feed(url)
                    if text:
                        print(f"    [DEBUG] dc_ feed длина={len(text)}")
                        for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
                            key, sep, value = chunk.partition(FIELD_SEP)
                            if sep:
                                key = key.strip()
                                value = value.strip()
                                if key == "AB":
                                    try:
                                        match.start_ts = int(float(value.strip()))
                                        print(f"    [DEBUG] start_ts из dc_ AB: {match.start_ts}")
                                        break
                                    except (ValueError, TypeError):
                                        pass
                                elif key == "AD":
                                    try:
                                        match.start_ts = int(float(value.strip()))
                                        print(f"    [DEBUG] start_ts из dc_ AD: {match.start_ts}")
                                        break
                                    except (ValueError, TypeError):
                                        pass
                    else:
                        print(f"    [DEBUG] dc_ feed пустой")
                except Exception as exc:
                    print(f"    [!] dc_ feed для start_ts: {exc}")
    
    if match.start_ts:
        print(f"    [OK] start_ts установлен: {match.start_ts}")
    else:
        print(f"    [!] start_ts всё ещё пустой после всех попыток")
    
    # Определяем статус матча ДО загрузки данных анализа:
    # завершён (status 3) → историческая таблица, иначе → текущий API.
    match.status = _fetch_match_status(match.match_id, settings.sport)
    if match.status is not None:
        print(f"    Статус матча (для загрузки данных): {match.status}")

    payload = load_analysis_data(match, settings)

    if not match.league and payload.h2h:
        match.league = payload.h2h[0].tour_name
    if not match.home and payload.h2h:
        match.home = payload.h2h[0].home_name
    if not match.away and payload.h2h:
        match.away = payload.h2h[0].away_name

    code, odds_data = load_odds(match.match_id, settings.source)
    if code != 0 or odds_data is None:
        odds_data = build_fallback_odds(match.match_id)
        if odds_data is None:
            reasons = {2: "нет коэффициентов в API", 3: "нет ID участников в API"}
            reason = reasons.get(code, f"код {code}")
            raise RuntimeError(f"odds_service: {reason} для {match.match_id}")
        print(
            f"[!] {match.match_id}: линия букмекеров недоступна "
            f"(код {code}), анализ без коэффициентов БК"
        )

    if odds_data.home_id and not match.home_participant_id:
        match.home_participant_id = odds_data.home_id
    if odds_data.away_id and not match.away_participant_id:
        match.away_participant_id = odds_data.away_id
    payload.match = match

    list_odds = _list_odds_from_queue(queued)

    own_engine = engine is None
    if own_engine:
        engine = get_calc_engine()
        engine.__enter__()
    try:
        results = engine.run(payload, odds_data, list_odds=list_odds)
    finally:
        if own_engine:
            engine.__exit__(None, None, None)

    db_sport = queue_sport_id(queued.sport) if queued and queued.sport else queue_sport_id(settings.sport)
    results["match_id"] = match.match_id
    results["sport"] = db_sport
    results["start_ts"] = queued.start_ts if queued else None

    # Статус уже определён до load_analysis_data; переиспользуем.
    match_status = match.status if match.status is not None else _fetch_match_status(match.match_id, settings.sport)
    results["match_status"] = match_status
    if match_status is not None:
        print(f"    Статус матча: {match_status}")

    if db_sport == 1 and strat_on(4):
        bts = compute_bts_prediction(
            match.match_id,
            match.home,
            match.away,
            settings,
            odds_data=odds_data,
        )
        if bts:
            results["prediction_bts"] = bts["prediction"]
            results["bts_odds"] = bts.get("odds")
            results["bts_notes"] = bts.get("notes")
            print(
                f"    BTS={bts['prediction']} @ {bts.get('odds')} "
                f"rate={float(bts.get('btts_rate') or 0)*100:.0f}% "
                f"edge={float(bts.get('difference') or 0)*100:+.1f}pp"
            )

    try:
        inj = fetch_and_store_for_match(match.match_id)
        if inj.get("players"):
            print(f"    Injuries: {inj['players']} absent ({inj['injuries']} injury)")
    except Exception as exc:
        print(f"    [!] injuries fetch: {exc}")

    try:
        info = save_match_info(
            match.match_id,
            sport=settings.sport,
            sourcer=settings.sourcer,
        )
        if info:
            print(f"    Инфо: {describe_match_info(info)}")
            
            # Рассчитываем расстояние между домашними стадионами команд
            if match.home and match.away:
                try:
                    from venues import get_team_home_venue
                    
                    home_venue_data = get_team_home_venue(match.home)
                    away_venue_data = get_team_home_venue(match.away)
                    
                    if home_venue_data and away_venue_data:
                        home_venue, home_town = home_venue_data
                        away_venue, away_town = away_venue_data
                        
                        distance = calculate_and_save_venue_distance(
                            home_venue, home_town,
                            away_venue, away_town
                        )
                        if distance:
                            print(f"    Расстояние: {distance} км ({home_venue} — {away_venue})")
                        else:
                            print(f"    [!] расстояние не рассчитано (нет координат): {home_venue} / {away_venue}")
                    else:
                        print(f"    [!] нет данных о стадионах: home={home_venue_data}, away={away_venue_data}")
                except Exception as dist_exc:
                    print(f"    [!] расчёт расстояния: {dist_exc}")
    except Exception as exc:
        print(f"    [!] инфо о матче: {exc}")
        info = {}

    if info.get("town"):
        try:
            weather = save_weather_snapshot(
                match.match_id,
                venue=str(info.get("venue") or ""),
                town=str(info["town"]),
                start_ts=queued.start_ts if queued else None,
                date_match=match.date or (queued.date_match if queued else ""),
                local_utc_offset=settings.timezone + settings.time_offset,
            )
            if weather:
                print(f"    Погода: {describe_weather(weather)}")
        except Exception as exc:
            print(f"    [!] погода: {exc}")

    # Проверка: если матч прошёл, восстанавливаем исторические данные
    match_status = results.get("match_status")
    if match_status is None and match.status is not None:
        match_status = match.status
    # Матч считается завершённым ТОЛЬКО по статусу 3 (полный матч).
    # start_ts есть и у будущих матчей, поэтому на него опираться нельзя.
    is_archived = match_status == 3
    if is_archived and match.start_ts:
        print(f"    [ARCHIVE] Матч прошёл, восстанавливаю исторические данные...")
        try:
            from archive_old_match import (
                fetch_tournament_matches,
                reconstruct_standings_before,
            )
            from tournament_resolver import resolve_tournament_keys
            from team_history import fetch_team_matches_before
            from flashscore_feed import clean_team_name

            # Определяем параметры турнира: резолвим tournament_key + season_id
            # из страницы матча (pageinfo -> season_list -> results seasonId).
            country_id = match.country_id or "198"
            tournament_key, season_id, _ = resolve_tournament_keys(match.match_id)

            print(f"    [DEBUG] tournament_key={tournament_key}, season_id={season_id}, country_id={country_id}")

            # Fallback: если резолвер не дал ключи (сеть/старый матч) — пробуем dc_ фид
            if not tournament_key:
                from flashscore_feed import FIELD_SEP, ROW_SEP, fetch_feed, FLASHSCORE_SOURCER
                url = f"https://{FLASHSCORE_SOURCER}x/feed/dc_{settings.sport}_{match.match_id}"
                try:
                    text = fetch_feed(url)
                    for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
                        key, sep, value = chunk.partition(FIELD_SEP)
                        if sep:
                            key = key.strip()
                            value = value.strip()
                            if key == "ZEE" and not tournament_key:
                                tournament_key = value
                                print(f"    [DEBUG] tournament_key из dc_: {tournament_key}")
                except Exception as exc:
                    print(f"    [!] dc_ feed для tournament: {exc}")

            # Создаём копию payload для исторических данных
            from analysis_data import AnalysisPayload
            hist_payload = AnalysisPayload(
                match=match,
                settings=settings,
            )

            if tournament_key and season_id:
                # 1) Загружаем все матчи турнира
                all_matches = fetch_tournament_matches(
                    settings.sport, int(country_id), tournament_key, season_id
                )

                # Находим целевой матч
                target = next(
                    (
                        m
                        for m in all_matches
                        if m["match_id"] == match.match_id
                    ),
                    None,
                )

                if target:
                    kickoff_ts = target["kickoff_ts"]

                    # 2) Восстанавливаем таблицу на момент матча
                    standings = reconstruct_standings_before(
                        all_matches, kickoff_ts
                    )
                    hist_payload.table_overall = [
                        type("TableRow", (), {
                            "rank": s["rank"], "team": s["team"],
                            "played": str(s["played"]), "wins": str(s["wins"]),
                            "draws": str(s["draws"]), "losses": str(s["losses"]),
                            "scored": str(s["scored"]), "conceded": str(s["conceded"]),
                            "points": str(s["points"]),
                        })() for s in standings["overall"]
                    ]
                    hist_payload.table_home = [
                        type("TableRow", (), {
                            "rank": s["rank"], "team": s["team"],
                            "played": str(s["played"]), "wins": str(s["wins"]),
                            "draws": str(s["draws"]), "losses": str(s["losses"]),
                            "scored": str(s["scored"]), "conceded": str(s["conceded"]),
                            "points": str(s["points"]),
                        })() for s in standings["home"]
                    ]
                    hist_payload.table_away = [
                        type("TableRow", (), {
                            "rank": s["rank"], "team": s["team"],
                            "played": str(s["played"]), "wins": str(s["wins"]),
                            "draws": str(s["draws"]), "losses": str(s["losses"]),
                            "scored": str(s["scored"]), "conceded": str(s["conceded"]),
                            "points": str(s["points"]),
                        })() for s in standings["away"]
                    ]

                    # 3) Загружаем исторические матчи команд (pr_ feed)
                    home_key = target.get("home_key", "")
                    away_key = target.get("away_key", "")
                    home_name = clean_team_name(target["home_name"])
                    away_name = clean_team_name(target["away_name"])

                    # Матчи команд ДО целевого матча
                    home_limit = 40
                    away_limit = 40

                    # Форматируем матч в HistoryMatch.
                    # Полный счёт кладём в home_ht/away_ht (как в fetch_h2h),
                    # venue — "Дома"/"Гости" относительно анализируемой команды
                    # (иначе ДомаДома!L/M = IF(I="Дома",J,K) дают пусто → 0 голов).
                    def _to_history_match(m: dict, team_name: str) -> "HistoryMatch":
                        from analysis_data import HistoryMatch
                        from team_history import format_match_date
                        is_home_team = m.get("home_name") == team_name
                        venue = "Дома" if is_home_team else "Гости"
                        return HistoryMatch(
                            tour_name=m.get("competition", ""),
                            date=m.get("match_date") or format_match_date(m.get("kickoff_ts") or 0),
                            home_name=m["home_name"],
                            away_name=m["away_name"],
                            home_ht=m.get("home_score") or 0,
                            away_ht=m.get("away_score") or 0,
                            home_st=0,
                            away_st=0,
                            venue=venue,
                        )

                    if home_key:
                        # H2H — оставляем как было (из df_hh/load_analysis_data),
                        # только убираем матчи ПОСЛЕ анализируемого.
                        from date_utils import parse_match_datetime
                        h2h_filtered = []
                        for hm in (payload.h2h or []):
                            try:
                                hdt = parse_match_datetime(hm.date)
                            except Exception:
                                h2h_filtered.append(hm)
                                continue
                            if hdt is None:
                                h2h_filtered.append(hm)
                                continue
                            # отфильтровать матчи с датой >= кик-оффа
                            from datetime import datetime
                            try:
                                kickoff_dt = datetime.fromtimestamp(kickoff_ts, tz=hdt.tzinfo or timezone.utc).replace(tzinfo=hdt.tzinfo or timezone.utc)
                                hdt_ts = hdt.timestamp()
                                kickoff_dt_ts = kickoff_dt.timestamp()
                            except (OSError, ValueError, OverflowError):
                                h2h_filtered.append(hm)
                                continue
                            if hdt_ts < kickoff_dt_ts:
                                h2h_filtered.append(hm)
                        hist_payload.h2h = h2h_filtered
                        hist_payload.h2h_home = list(payload.h2h_home or [])

                        # Матчи хозяев до целевого: сначала кэш (архив matches),
                        # затем догрузка pr_ фидом, если меньше limit.
                        home_pr = _cached_team_matches(
                            home_name, kickoff_ts,
                            home_key=home_key, country=int(country_id),
                            sport=settings.sport, limit=home_limit,
                        )
                        home_hist = home_pr[-home_limit:]
                        home_all = [
                            m for m in home_hist
                            if m["home_name"] == home_name or m["away_name"] == home_name
                        ]
                        hist_payload.home_all = [_to_history_match(m, home_name) for m in home_all]
                        hist_payload.home_home = [
                            _to_history_match(m, home_name) for m in home_all if m["home_name"] == home_name
                        ]
                        hist_payload.home_away = [
                            _to_history_match(m, home_name) for m in home_all if m["away_name"] == home_name
                        ]
                        print(f"    [OK] Home team: {len(hist_payload.home_all)} матчей, H2H: {len(hist_payload.h2h)}")

                    if away_key:
                        away_pr = _cached_team_matches(
                            away_name, kickoff_ts,
                            home_key=away_key, country=int(country_id),
                            sport=settings.sport, limit=away_limit,
                        )
                        away_hist = away_pr[-away_limit:]

                        away_all = [
                            m for m in away_hist
                            if m["home_name"] == away_name or m["away_name"] == away_name
                        ]
                        hist_payload.away_all = [_to_history_match(m, away_name) for m in away_all]
                        hist_payload.away_home = [
                            _to_history_match(m, away_name) for m in away_all if m["home_name"] == away_name
                        ]
                        hist_payload.away_away = [
                            _to_history_match(m, away_name) for m in away_all if m["away_name"] == away_name
                        ]

                        print(f"    [OK] Away team: {len(hist_payload.away_all)} матчей")

                    # История команд уже сохранена в кэш `team_matches_cache`
                    # внутри _cached_team_matches (НЕ в таблицу matches).

                    # 4) Сохраняем все исторические данные (таблица + матчи команд + H2H)
                    try:
                        saved = save_payload_snapshot(match.match_id, hist_payload)
                        if saved:
                            print(f"    Снимок: {describe_payload_snapshot(hist_payload)}")
                        else:
                            # fallback: сохранить хотя бы таблицу вручную
                            from db import upsert_match_snapshot
                            upsert_match_snapshot(
                                match.match_id,
                                {"standings_json": json.dumps(standings, ensure_ascii=False)},
                            )
                            print(f"    [OK] Историческая таблица: overall={len(standings['overall'])} "
                                  f"home={len(standings['home'])} away={len(standings['away'])} команд")
                    except Exception as snap_exc:
                        print(f"    [!] снимок исторических данных: {snap_exc}")

                    # 4.5) Пересчёт на реконструированных данных: вероятность голов
                    # и прогнозы стратetий (NTB/Betalone/Sniper зависят от голов и тоталов).
                    try:
                        hist_payload.match = match
                        hist_payload.settings = settings
                        _eng = engine if engine is not None else get_calc_engine()
                        hist_results = _eng.run(hist_payload, odds_data, list_odds=list_odds)
                        if hist_results.get("home_goals") or hist_results.get("away_goals"):
                            results["home_goals"] = hist_results["home_goals"]
                            results["away_goals"] = hist_results["away_goals"]
                            results["outcome_probabilities"] = hist_results.get("outcome_probabilities") or results.get("outcome_probabilities")
                            print(f"    [OK] Вероятности голов пересчитаны (h={len(results['home_goals'])} a={len(results['away_goals'])})")
                        # Пересчитываем прогнозы стратегий (зависят от тотала/вероятностей)
                        for key in ("prediction_ntb", "prediction_betalone", "prediction_sniper"):
                            new_val = hist_results.get(key)
                            if new_val not in (None, ""):
                                old_val = results.get(key)
                                if new_val != old_val:
                                    print(f"    [RERUN] {key}: {old_val!r} -> {new_val!r}")
                                results[key] = new_val
                    except Exception as recalc_exc:
                        print(f"    [!] пересчёт вероятностей голов: {recalc_exc}")
                else:
                    print(f"    [!] Целевой матч не найден в турнире")
                    # Fallback: payload
                    try:
                        if save_payload_snapshot(match.match_id, payload):
                            print(f"    Снимок: {describe_payload_snapshot(payload)}")
                    except Exception as inner_exc:
                        print(f"    [!] снимок данных анализа: {inner_exc}")
            else:
                print(f"    [!] Нет tournament_key/season_id для восстановления")
                # Fallback: payload
                try:
                    if save_payload_snapshot(match.match_id, payload):
                        print(f"    Снимок: {describe_payload_snapshot(payload)}")
                except Exception as inner_exc:
                    print(f"    [!] снимок данных анализа: {inner_exc}")
        except Exception as exc:
            print(f"    [!] восстановление исторических данных: {exc}")
            import traceback
            traceback.print_exc()
            # Fallback: payload
            try:
                if save_payload_snapshot(match.match_id, payload):
                    print(f"    Снимок: {describe_payload_snapshot(payload)}")
            except Exception as inner_exc:
                print(f"    [!] снимок данных анализа: {inner_exc}")
    else:
        # Матч не прошёл — берём данные через API (payload)
        try:
            if save_payload_snapshot(match.match_id, payload):
                print(f"    Снимок: {describe_payload_snapshot(payload)}")
        except Exception as exc:
            print(f"    [!] снимок данных анализа: {exc}")

    # Сбор статистики матча
    try:
        stats = fetch_match_stats(match.match_id, sport=settings.sport, sourcer=settings.sourcer)
        if stats:
            save_match_stats(match.match_id, stats)
            # Выводим основную статистику матча
            match_data = stats.get("match", {})
            if match_data:
                shots_on_target = match_data.get("Главное_Удары в створ", {})
                if shots_on_target:
                    print(
                        f"    Статистика: удары в створ {shots_on_target.get('home', 0)}:{shots_on_target.get('away', 0)}"
                    )
    except Exception as exc:
        print(f"    [!] статистика матча: {exc}")

    # Анализ формы команд (последние 5 матчей)
    # Для прошедших матчей фильтруем по доте кик-оффа
    form_before_ts = match.start_ts if match_status == 3 and match.start_ts else None
    try:
        if match.home and match.away:
            # Анализ формы хозяев
            home_form = analyze_team_form(match.home, limit=5, before_ts=form_before_ts)
            if home_form.get("status") == "ok":
                save_team_stats_to_db(match.home, home_form)
                goals = home_form.get("goals", {})
                results_data = home_form.get("results", {})
                print(
                    f"    Форма {match.home}: "
                    f"{results_data.get('wins', 0)}W/{results_data.get('draws', 0)}D/{results_data.get('losses', 0)}L "
                    f"| голы {goals.get('scored', 0):.1f}:{goals.get('conceded', 0):.1f}"
                )
            
            # Анализ формы гостей
            away_form = analyze_team_form(match.away, limit=5, before_ts=form_before_ts)
            if away_form.get("status") == "ok":
                save_team_stats_to_db(match.away, away_form)
                goals = away_form.get("goals", {})
                results_data = away_form.get("results", {})
                print(
                    f"    Форма {match.away}: "
                    f"{results_data.get('wins', 0)}W/{results_data.get('draws', 0)}D/{results_data.get('losses', 0)}L "
                    f"| голы {goals.get('scored', 0):.1f}:{goals.get('conceded', 0):.1f}"
                )
    except Exception as form_exc:
        print(f"    [!] форма команд: {form_exc}")

    if strat_on(5):
        fav = compute_favorites_win_prediction(
            match.match_id,
            db_sport,
            odds_data=odds_data,
            odds_home=list_odds[0] if list_odds else None,
            odds_away=list_odds[2] if list_odds else None,
        )
        if fav:
            results["prediction_favorites"] = fav["prediction"]
            results["favorites_odds"] = fav.get("odds")
            results["favorites_notes"] = fav.get("notes")
            band = fav.get("odds_range") or {}
            print(
                f"    Favorites (#5)={fav.get('label')} @ {fav.get('odds')} "
                f"range={band.get('min')}–{band.get('max')}"
            )

    if strat_on(6):
        stavka = compute_stavka_tv_prediction(
            match.match_id,
            match.home,
            match.away,
            db_sport,
        )
        if stavka:
            results["prediction_stavka"] = stavka["prediction"]
            results["stavka_odds"] = stavka.get("odds")
            results["stavka_notes"] = stavka.get("notes")
            print(f"    StavkaTV (#6)={stavka['prediction']} @ {stavka.get('odds')}")

    # Догз/Moneyway: на сайте Arbworld данные есть только для будущих матчей,
    # поэтому для завершённых матчей стратегию не считаем вовсе.
    if db_sport == 1 and strat_on(7) and match_status != 3:
        from dogs_strategy import last_arbworld_error

        if arbworld_index is None and last_arbworld_error():
            results["moneyway"] = {
                "home_name": match.home,
                "away_name": match.away,
                "found": False,
                "has_signal": False,
                "raw_json": f'{{"error": "{last_arbworld_error()}"}}',
            }
        else:
            try:
                missing_aw = _ensure_service_aliases(match.home, match.away, "arbworld")
                if missing_aw:
                    print(f"    [!] Arbworld/dogs: нет имён в БД для: {', '.join(missing_aw)} (fuzzy-поиск)")
                snap = build_moneyway_snapshot(
                    match.home,
                    match.away,
                    sport=db_sport,
                    arbworld_index=arbworld_index,
                )
                if snap:
                    results["moneyway"] = snap
                    if snap.get("found"):
                        vols = (
                            f"v1={snap.get('volume_1')} "
                            f"vx={snap.get('volume_x')} "
                            f"v2={snap.get('volume_2')}"
                        )
                        print(
                            f"    Moneyway data: found "
                            f"c={snap.get('coef_1')}/{snap.get('coef_x')}/{snap.get('coef_2')} {vols}"
                        )
                    else:
                        print("    Moneyway data: not in Arbworld")
                    if snap.get("has_signal") and snap.get("signal_side"):
                        results["prediction_dogs"] = snap["signal_side"]
                        results["dogs_odds"] = snap.get("signal_odds")
                        results["dogs_notes"] = snap.get("notes") or snap.get("raw_json")
                        print(
                            f"    Moneyway (#7)={snap['signal_side']} @ {snap.get('signal_odds')}"
                        )
            except Exception as exc:
                print(f"    [!] Moneyway (#7): {exc}")

    if db_sport == 1 and strat_on(9):
        try:
            # Спрашиваем имена ДО проверки missing: иначе только что введённый
            # alias считался бы отсутствующим (как раньше с 'Уотфорд').
            _ensure_service_aliases(match.home, match.away, "whoscored")
            missing_ws = [
                nm
                for nm in (match.home, match.away)
                if (nm or "").strip()
                and not get_service_team_name(nm.strip(), "whoscored")
            ]
            if missing_ws:
                print(f"    [!] WhoScored: нет имён в БД для: {', '.join(missing_ws)} (пропуск по маппингу)")
            ws = compute_whoscored_prediction(
                match.match_id,
                match.home,
                match.away,
                match.league or (queued.tour_name if queued else ""),
                match.date or (queued.date_match if queued else ""),
                sport=db_sport,
                odds_data=odds_data,
                previews=whoscored_index,
            )
            if ws:
                results["prediction_whoscored"] = ws["prediction"]
                results["whoscored_odds"] = ws.get("odds")
                results["whoscored_notes"] = ws.get("notes")
                print(
                    f"    WhoScored (#9)={ws['prediction']} "
                    f"cs@{ws.get('cs_odds')} ah@{ws.get('ah_odds')}"
                )
        except Exception as exc:
            print(f"    [!] WhoScored (#9): {exc}")

    # XGBoost (#10)
    if strat_on(10):
        try:
            xgb = XGBoostStrategy()
            xgb_ctx = MatchContext(
                match_id=match.match_id,
                home=match.home,
                away=match.away,
                sport=db_sport,
                odds_data=odds_data,
            )
            xgb_signal = xgb.evaluate(xgb_ctx)
            if xgb_signal:
                results["prediction_xgboost"] = xgb_signal.prediction
                results["xgboost_odds"] = xgb_signal.odds
                results["xgboost_notes"] = xgb_signal.notes
                print(
                    f"    XGBoost (#10)={xgb_signal.prediction} @ {xgb_signal.odds} "
                    f"prob={xgb_signal.extra.get('probability', 0):.3f}"
                )
        except Exception as exc:
            print(f"    [!] XGBoost (#10): {exc}")

    if save_to_db:
        pred_ntb = results.get("prediction_ntb")
        pred_sniper = results.get("prediction_sniper")
        # Если считаем только доп. стратегии (без calc 1/2/3) — не требуем главный прогноз.
        calc_selected = (
            only_strategies is None
            or bool({1, 2, 3} & only_strategies)
        )
        if calc_selected:
            if pred_ntb in (None, "") and pred_sniper in (None, ""):
                raise RuntimeError("Анализ не дал прогноза")
            if str(pred_ntb).startswith("#") or str(pred_sniper).startswith("#"):
                raise RuntimeError("Анализ вернул ошибку формул Excel")
        # Счёт матча из dc_ фида (для архивных/завершённых матчей).
        if match_status == 3 and results.get("score_home") in (None, ""):
            sh, sa = _fetch_match_score(match.match_id, settings.sport)
            if sh is not None and sa is not None:
                results["score_home"] = sh
                results["score_away"] = sa
                print(f"    Счёт матча: {sh}:{sa}")

        # Коэффициенты для прогнозов: любой прогноз → канонический рынок.
        odds_markets = odds_data.all_markets_flat()
        market_lookup = odds_lookup(odds_markets)

        if pred_ntb:
            results["odds_ntb"] = resolve_prediction_odds(str(pred_ntb), market_lookup)
        if pred_sniper:
            results["odds_sniper"] = resolve_prediction_odds(str(pred_sniper), market_lookup)

        save_analysis_to_db(
            match.match_id,
            db_sport,
            results,
            odds_markets=odds_markets,
            partial=not calc_selected,
        )

    return results


def run_cli(workbook: str, match_id: str, **kwargs) -> int:
    create_database()
    settings = DeluxSettings.from_env().match_settings
    match = MatchInfo(match_id=match_id, **{k: v for k, v in kwargs.items() if v})
    results = analyze_match(workbook, match, settings)
    print(f"[+] Анализ {match_id} завершён")
    print(f"    NTB (S13): {results.get('prediction_ntb')}")
    print(f"    Betalone (O10): {results.get('prediction_betalone')}")
    print(f"    Sniper (X24): {results.get('prediction_sniper')}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Анализ матча DeluX")
    parser.add_argument("--workbook", default="")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--league", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--home", default="")
    parser.add_argument("--away", default="")
    parser.add_argument("--country-id", default="")
    args = parser.parse_args()
    try:
        cfg = DeluxSettings.from_env()
        workbook = args.workbook or ""
        raise SystemExit(
            run_cli(
                workbook,
                args.match_id,
                league=args.league,
                date=args.date,
                home=args.home,
                away=args.away,
                country_id=args.country_id,
            )
        )
    except Exception as exc:
        print(f"[-] {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
