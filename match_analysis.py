"""Анализ матча: данные из API → calc .xlsm → сохранение в БД."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from analysis_data import AnalysisPayload, MatchInfo, MatchSettings, build_settings, load_analysis_data
from bts_strategy import BTS_STRATEGY_ID, compute_bts_prediction
from dogs_strategy import DOGS_STRATEGY_ID, build_moneyway_snapshot
from favorites_strategy import FAVORITES_STRATEGY_ID, compute_favorites_win_prediction
from stavka_tv_strategy import STAVKA_TV_STRATEGY_ID, compute_stavka_tv_prediction
from favorites_stats.injuries import fetch_and_store_for_match
from calc_backend import CalcEngine, get_calc_engine
from db import (
    create_database,
    get_db_connection,
    insert_goal_probabilities_from_values,
    insert_or_get_country,
    insert_or_get_league,
    insert_or_get_team,
    insert_outcome_probabilities_from_values,
    parse_league,
    upsert_moneyway,
)
from match_store import QueuedMatch
from odds_service import build_fallback_odds, load_odds
from settings import DeluxSettings, queue_sport_id
from date_utils import normalize_match_date


def save_analysis_to_db(
    match_id: str,
    sport: int,
    results: Dict[str, Any],
    odds_markets: Optional[list] = None,
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
        cursor.execute(
            """
            INSERT OR REPLACE INTO matches
            (match_id, match_date, league_id, home_team_id, away_team_id, prediction, sport)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                normalize_match_date(results.get("match_date") or ""),
                league_id,
                home_team_id,
                away_team_id,
                prediction,
                sport,
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
    return True


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
) -> Dict[str, Any]:
    settings = settings or build_settings()
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

    if db_sport == 1:
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

    if db_sport == 1:
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

    if save_to_db:
        pred_ntb = results.get("prediction_ntb")
        pred_sniper = results.get("prediction_sniper")
        if pred_ntb in (None, "") and pred_sniper in (None, ""):
            raise RuntimeError("Анализ не дал прогноза")
        if str(pred_ntb).startswith("#") or str(pred_sniper).startswith("#"):
            raise RuntimeError("Анализ вернул ошибку формул Excel")
        save_analysis_to_db(
            match.match_id,
            db_sport,
            results,
            odds_markets=odds_data.all_markets_flat(),
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
        workbook = args.workbook or cfg.resolve_calc_workbook()
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
