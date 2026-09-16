from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import pandas as pd

from odds_normalize import canonicalize_market
from src.ml.database import DatabaseCatalog

LABEL_COLUMNS = ["target_1x2", "target_over_2_5"]
IDENTIFIER_COLUMNS = ["match_id", "kickoff_ts", "match_date"]
CATEGORICAL_COLUMNS = [
    "sport",
    "league_id",
    "home_team_id",
    "away_team_id",
    "referee_country",
    "venue",
    "town",
    "ws_home_formation",
    "ws_away_formation",
]
LEAKAGE_COLUMNS = {
    "score_home",
    "score_away",
    "match_status",
    "minute",
    "segment",
    "profit",
    "attendance",
    "weather_actual",
}
SAFE_MARKETS = {
    "1X2_1": "odds_1",
    "1X2_X": "odds_x",
    "1X2_2": "odds_2",
    "OVER 2.5": "odds_over_2_5",
    "UNDER 2.5": "odds_under_2_5",
    "BTTS_YES": "odds_btts_yes",
    "BTTS_NO": "odds_btts_no",
}


@dataclass
class FeatureDataset:
    frame: pd.DataFrame
    feature_columns: List[str]
    categorical_columns: List[str]


def _json(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (ValueError, TypeError):
        return fallback


def _number(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _mean(values: Iterable[Any]) -> float:
    numbers = [_number(value) for value in values]
    numbers = [value for value in numbers if not math.isnan(value)]
    return sum(numbers) / len(numbers) if numbers else math.nan


def _kickoff_epoch(row: Dict[str, Any]) -> float:
    value = _number(row.get("match_start_ts"))
    if not math.isnan(value):
        return value
    parsed = pd.to_datetime(row.get("match_date"), errors="coerce")
    if pd.isna(parsed):
        return math.nan
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
        return float(parsed.timestamp() - 3 * 3600)
    return float(parsed.timestamp())


def _is_pre_match(row: Dict[str, Any], fetched_at: Any) -> bool:
    if not fetched_at:
        return True
    kickoff = _kickoff_epoch(row)
    fetched = pd.to_datetime(fetched_at, errors="coerce", utc=True)
    if math.isnan(kickoff) or pd.isna(fetched):
        return True
    return float(fetched.timestamp()) <= kickoff


def _team_row(rows: List[Dict[str, Any]], team: str) -> Dict[str, Any]:
    key = (team or "").strip().casefold()
    return next(
        (row for row in rows if str(row.get("team") or "").strip().casefold() == key),
        {},
    )


def _table_features(raw: Any, home: str, away: str) -> Dict[str, Any]:
    data = _json(raw, {})
    rows = data.get("overall") or []
    result: Dict[str, Any] = {}
    for prefix, team in (("home", home), ("away", away)):
        row = _team_row(rows, team)
        for field in ("rank", "played", "wins", "draws", "losses", "scored", "conceded", "points"):
            result[f"table_{prefix}_{field}"] = _number(row.get(field))
    return result


def _history_features(raw: Any) -> Dict[str, Any]:
    data = _json(raw, {})
    home_games = ((data.get("home") or {}).get("all") or [])[:10]
    away_games = ((data.get("away") or {}).get("all") or [])[:10]
    result: Dict[str, Any] = {}
    for prefix, games in (("home", home_games), ("away", away_games)):
        totals = [_number(g.get("home_ht")) + _number(g.get("away_ht")) for g in games]
        result[f"history_{prefix}_games"] = len(games)
        result[f"history_{prefix}_avg_total"] = _mean(totals)
        result[f"history_{prefix}_avg_home_goals"] = _mean(g.get("home_ht") for g in games)
        result[f"history_{prefix}_avg_away_goals"] = _mean(g.get("away_ht") for g in games)
    return result


def _h2h_features(raw: Any) -> Dict[str, Any]:
    games = (_json(raw, {}).get("all") or [])[:10]
    totals = [_number(g.get("home_ht")) + _number(g.get("away_ht")) for g in games]
    return {
        "h2h_games": len(games),
        "h2h_avg_total": _mean(totals),
        "h2h_home_win_rate": _mean(
            1.0 if _number(g.get("home_ht")) > _number(g.get("away_ht")) else 0.0
            for g in games
        ),
    }


def _weather_features(raw: Any) -> Dict[str, Any]:
    data = _json(raw, {})
    fields = (
        "lead_hours",
        "temperature_c",
        "apparent_temperature_c",
        "wind_ms",
        "gust_ms",
        "precipitation_mm",
        "precipitation_probability",
        "snowfall_cm",
        "cloud_pct",
        "humidity_pct",
        "weather_code",
        "roof",
    )
    return {f"weather_{field}": _number(data.get(field)) for field in fields}


def _base_rows(catalog: DatabaseCatalog, training: bool) -> List[Dict[str, Any]]:
    tables = set(catalog.tables())
    queue_join = (
        """
        LEFT JOIN match_queue q ON q.match_id = m.match_id
        """
        if "match_queue" in tables
        else ""
    )
    queue_cols = (
        """
        q.start_home AS queue_odds_1, q.start_draw AS queue_odds_x,
        q.start_away AS queue_odds_2, q.loaded_at AS queue_loaded_at,
        """
        if "match_queue" in tables
        else "NULL AS queue_odds_1, NULL AS queue_odds_x, NULL AS queue_odds_2, NULL AS queue_loaded_at,"
    )
    where = (
        """
        WHERE m.match_status = 'Завершен'
          AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
          AND TRIM(m.match_id) != ''
        """
        if training
        else "WHERE COALESCE(m.match_status, 'Не начался') != 'Завершен' AND TRIM(m.match_id) != ''"
    )
    main_query = f"""
        SELECT m.match_id, m.match_date, m.start_ts AS match_start_ts,
               m.sport, m.league_id, m.home_team_id, m.away_team_id,
               ht.name AS home_name, at.name AS away_name,
               {queue_cols}
               m.score_home, m.score_away
        FROM matches m
        LEFT JOIN teams ht ON ht.id = m.home_team_id
        LEFT JOIN teams at ON at.id = m.away_team_id
        {queue_join}
        {where}
        """
    if not training and "match_queue" in tables:
        main_query += """
        UNION ALL
        SELECT q.match_id, q.date_match, q.start_ts,
               q.sport, NULL, ht.id, at.id, q.home_name, q.away_name,
               q.start_home, q.start_draw, q.start_away, q.loaded_at,
               NULL, NULL
        FROM match_queue q
        LEFT JOIN teams ht ON ht.name = q.home_name
        LEFT JOIN teams at ON at.name = q.away_name
        WHERE TRIM(q.match_id) != ''
          AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.match_id=q.match_id)
        """
    return catalog.query(main_query)


def _index_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row["match_id"]): row for row in rows}


def _add_odds(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "odds" not in catalog.tables():
        return
    rows = catalog.query(
        "SELECT match_id, market_name, outcome, side, line_value, odds_value FROM odds"
    )
    for row in rows:
        target = data.get(str(row["match_id"]))
        if target is None:
            continue
        key = canonicalize_market(
            row.get("market_name"),
            outcome=row.get("outcome"),
            side=row.get("side"),
            line_value=row.get("line_value"),
        )
        feature = SAFE_MARKETS.get(str(key or "").upper())
        value = _number(row.get("odds_value"))
        if feature and not math.isnan(value):
            target[feature] = max(value, _number(target.get(feature))) if feature in target else value


def _add_snapshots(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "match_snapshot" not in catalog.tables():
        return
    columns = {column["name"] for column in catalog.columns("match_snapshot")}
    wanted = [
        name
        for name in (
            "match_id",
            "referee_country",
            "venue",
            "town",
            "capacity",
            "standings_json",
            "form_json",
            "h2h_json",
            "team_matches_json",
            "weather_json",
            "fetched_at",
        )
        if name in columns
    ]
    for row in catalog.query(f"SELECT {', '.join(wanted)} FROM match_snapshot"):
        target = data.get(str(row["match_id"]))
        if target is None:
            continue
        if not _is_pre_match(target, row.get("fetched_at")):
            continue
        for name in ("referee_country", "venue", "town"):
            target[name] = row.get(name) or ""
        target["capacity"] = _number(row.get("capacity"))
        target.update(_table_features(row.get("standings_json"), target["home_name"], target["away_name"]))
        target.update({f"form_{k[6:]}": v for k, v in _table_features(row.get("form_json"), target["home_name"], target["away_name"]).items()})
        target.update(_h2h_features(row.get("h2h_json")))
        target.update(_history_features(row.get("team_matches_json")))
        target.update(_weather_features(row.get("weather_json")))


def _add_missing(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "match_missing_players" not in catalog.tables():
        return
    rows = catalog.query(
        """
        SELECT match_id,
          SUM(CASE WHEN side='home' THEN 1 ELSE 0 END) AS missing_home,
          SUM(CASE WHEN side='away' THEN 1 ELSE 0 END) AS missing_away,
          SUM(CASE WHEN is_unsure=1 THEN 1 ELSE 0 END) AS missing_unsure,
          MAX(fetched_at) AS fetched_at
        FROM match_missing_players GROUP BY match_id
        """
    )
    for row in rows:
        target = data.get(str(row["match_id"]))
        if target is not None and _is_pre_match(target, row.get("fetched_at")):
            for name in ("missing_home", "missing_away", "missing_unsure"):
                target[name] = _number(row.get(name))


def _add_moneyway(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "moneyway" not in catalog.tables():
        return
    for row in catalog.query(
        """
        SELECT match_id, coef_1, coef_x, coef_2, volume_1, volume_x, volume_2,
               volume_floor, fetched_at FROM moneyway
        """
    ):
        target = data.get(str(row["match_id"]))
        if target is not None and _is_pre_match(target, row.get("fetched_at")):
            for name, value in row.items():
                if name not in ("match_id", "fetched_at"):
                    target[f"moneyway_{name}"] = _number(value)


def _add_whoscored(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "whoscored_preview" not in catalog.tables():
        return
    for row in catalog.query(
        """
        SELECT match_id, formation_home, formation_away, missing_json, lineups_json, fetched_at
        FROM whoscored_preview
        """
    ):
        target = data.get(str(row["match_id"]))
        if target is None:
            continue
        if not _is_pre_match(target, row.get("fetched_at")):
            continue
        missing = _json(row.get("missing_json"), {})
        lineups = _json(row.get("lineups_json"), {})
        target["ws_home_formation"] = row.get("formation_home") or ""
        target["ws_away_formation"] = row.get("formation_away") or ""
        target["ws_home_missing"] = len(missing.get("home") or [])
        target["ws_away_missing"] = len(missing.get("away") or [])
        target["ws_home_lineup"] = len((lineups.get("home") or {}).get("players") or [])
        target["ws_away_lineup"] = len((lineups.get("away") or {}).get("players") or [])


def _add_stacking(catalog: DatabaseCatalog, data: Dict[str, Dict[str, Any]]) -> None:
    if "outcome_probabilities" in catalog.tables():
        for row in catalog.query(
            """
            SELECT match_id, strategy_id, home_win_prob, draw_prob, away_win_prob
            FROM outcome_probabilities
            """
        ):
            target = data.get(str(row["match_id"]))
            if target is None:
                continue
            sid = int(row["strategy_id"])
            target[f"stack_s{sid}_p1"] = _number(row.get("home_win_prob"))
            target[f"stack_s{sid}_px"] = _number(row.get("draw_prob"))
            target[f"stack_s{sid}_p2"] = _number(row.get("away_win_prob"))
    if "goal_probabilities" in catalog.tables():
        for row in catalog.query("SELECT * FROM goal_probabilities"):
            target = data.get(str(row["match_id"]))
            if target is None:
                continue
            for name, value in row.items():
                if re.match(r"^(home|away)_goals_\d+$", name):
                    target[f"stack_{name}"] = _number(value)
    if "strategy_predictions" in catalog.tables():
        for row in catalog.query(
            "SELECT match_id, strategy_id, prediction, odds FROM strategy_predictions"
        ):
            target = data.get(str(row["match_id"]))
            if target is None:
                continue
            sid = int(row["strategy_id"])
            target[f"stack_strategy_{sid}_prediction"] = str(row.get("prediction") or "")
            target[f"stack_strategy_{sid}_odds"] = _number(row.get("odds"))


def build_feature_dataset(
    catalog: DatabaseCatalog,
    *,
    training: bool,
    include_stacking: bool = False,
) -> FeatureDataset:
    rows = _base_rows(catalog, training)
    data = _index_rows(rows)
    _add_odds(catalog, data)
    _add_snapshots(catalog, data)
    _add_missing(catalog, data)
    _add_moneyway(catalog, data)
    _add_whoscored(catalog, data)
    if include_stacking:
        _add_stacking(catalog, data)

    frame = pd.DataFrame(data.values())
    if frame.empty:
        return FeatureDataset(frame, [], [])
    frame["kickoff_ts"] = pd.to_numeric(frame["match_start_ts"], errors="coerce")
    parsed_dates = pd.to_datetime(frame["match_date"], errors="coerce", format="mixed")
    fallback_ts = pd.Series(float("nan"), index=frame.index)
    valid_dates = parsed_dates.notna()
    fallback_ts.loc[valid_dates] = parsed_dates.loc[valid_dates].astype("int64") / 1e9
    frame["kickoff_ts"] = frame["kickoff_ts"].fillna(fallback_ts)
    dt = pd.to_datetime(frame["kickoff_ts"], unit="s", errors="coerce", utc=True)
    frame["kickoff_month"] = dt.dt.month
    frame["kickoff_weekday"] = dt.dt.weekday
    frame["kickoff_hour"] = dt.dt.hour
    if all(name in frame for name in ("odds_1", "odds_x", "odds_2")):
        inverse = pd.DataFrame(
            {
                "p1": 1 / pd.to_numeric(frame["odds_1"], errors="coerce"),
                "px": 1 / pd.to_numeric(frame["odds_x"], errors="coerce"),
                "p2": 1 / pd.to_numeric(frame["odds_2"], errors="coerce"),
            }
        )
        overround = inverse.sum(axis=1)
        frame["implied_p1"] = inverse["p1"] / overround
        frame["implied_px"] = inverse["px"] / overround
        frame["implied_p2"] = inverse["p2"] / overround
    if all(name in frame for name in ("odds_over_2_5", "odds_under_2_5")):
        over = 1 / pd.to_numeric(frame["odds_over_2_5"], errors="coerce")
        under = 1 / pd.to_numeric(frame["odds_under_2_5"], errors="coerce")
        total = over + under
        frame["implied_over_2_5"] = over / total
    for name in CATEGORICAL_COLUMNS:
        if name not in frame:
            frame[name] = ""
        frame[name] = frame[name].fillna("").astype(str)

    if training:
        home = pd.to_numeric(frame["score_home"], errors="coerce")
        away = pd.to_numeric(frame["score_away"], errors="coerce")
        frame["target_1x2"] = 0
        frame.loc[home > away, "target_1x2"] = 1
        frame.loc[home < away, "target_1x2"] = 2
        frame["target_over_2_5"] = ((home + away) > 2.5).astype(int)

    excluded = set(IDENTIFIER_COLUMNS + LABEL_COLUMNS) | LEAKAGE_COLUMNS | {
        "match_start_ts",
        "home_name",
        "away_name",
        "queue_loaded_at",
    }
    feature_columns = sorted(column for column in frame.columns if column not in excluded)
    leakage = LEAKAGE_COLUMNS.intersection(feature_columns)
    if leakage:
        raise RuntimeError(f"Leakage columns in feature set: {sorted(leakage)}")
    categorical = [name for name in CATEGORICAL_COLUMNS if name in feature_columns]
    categorical.extend(
        name
        for name in feature_columns
        if name.startswith("stack_strategy_") and name.endswith("_prediction")
    )
    return FeatureDataset(frame, feature_columns, categorical)

