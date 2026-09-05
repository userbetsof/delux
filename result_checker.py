"""Проверка результатов матчей в БД (без листа achive)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from flashscore_feed import fetch_feed, iter_feed_rows, map_source, parse_fields
from matches_check import STATUSES, calc_forecast_result, parse_match_time
from settings import DeluxSettings


def _adjust_scores(first_home: int, first_away: int, second_home: int, second_away: int) -> Tuple[int, int]:
    first_home_adj = first_home - second_home
    first_away_adj = first_away - second_away
    return first_home_adj + second_home, first_away_adj + second_away


def _build_feed_index(sport_id: str, settings: DeluxSettings) -> Dict[str, dict]:
    ms = settings.match_settings
    url = f"https://{ms.sourcer}x/feed/f_{sport_id}_{settings.dayzone}_{settings.timezone}{ms.suffix}"
    feed = fetch_feed(url)
    index: Dict[str, dict] = {}
    for fs_index_name, _fs_index_value, fields in iter_feed_rows(feed):
        if fs_index_name != "AA":
            continue
        data = parse_fields(fields)
        match_id = data.get("AA", "")
        if match_id:
            index[match_id] = data
    return index


def run_db_check() -> int:
    from db import create_database, get_db_connection

    settings = DeluxSettings.from_env()
    create_database()

    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT m.match_id, m.sport, m.match_status,
                   sp.strategy_id, sp.prediction, sp.odds, sp.id AS sp_id
            FROM matches m
            LEFT JOIN strategy_predictions sp ON sp.match_id = m.match_id
            WHERE m.match_status NOT IN ('Завершен', 'После овертайма', 'После буллитов')
               OR m.match_status IS NULL
            """
        )
        rows = cur.fetchall()

    if not rows:
        print("[+] Нет матчей для проверки")
        return 0

    sports = sorted({str(r["sport"] or 1) for r in rows})
    feeds: Dict[str, Dict[str, dict]] = {}
    for sport_id in sports:
        feeds[sport_id] = _build_feed_index(sport_id, settings)

    updated = 0
    with get_db_connection() as conn:
        for row in rows:
            match_id = row["match_id"]
            sport = str(row["sport"] or 1)
            data = feeds.get(sport, {}).get(match_id)
            if not data:
                continue

            first_home = int(float(data.get("AT", "0") or 0))
            first_away = int(float(data.get("AU", "0") or 0))
            second_home = int(float(data.get("BC", "0") or 0))
            second_away = int(float(data.get("BD", "0") or 0))
            total_home, total_away = _adjust_scores(first_home, first_away, second_home, second_away)

            status_text = STATUSES.get(str(data.get("AC", "")), f"Неизвестный ({data.get('AC', '')})")
            period_text, minute_text = parse_match_time(str(data.get("BX", "")))
            result = "П1" if total_home > total_away else ("П2" if total_home < total_away else "X")

            conn.execute(
                """
                UPDATE matches SET
                    match_status = ?,
                    score_home = ?,
                    score_away = ?,
                    minute = ?
                WHERE match_id = ?
                """,
                (status_text, total_home, total_away, minute_text or period_text or "90+", match_id),
            )

            if row["sp_id"] and row["prediction"]:
                coeff = float(row["odds"] or 1.0)
                status, profit = calc_forecast_result(
                    str(row["prediction"]),
                    result,
                    total_home,
                    total_away,
                    coeff,
                )
                conn.execute(
                    """
                    UPDATE strategy_predictions SET result = ?, profit = ?
                    WHERE id = ?
                    """,
                    (status, profit, row["sp_id"]),
                )
            updated += 1

    print(f"[+] Обновлено матчей: {updated}")
    return 0
