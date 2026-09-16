"""Проверка результатов матчей в БД (без листа achive)."""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from date_utils import parse_match_datetime

from flashscore_feed import (
    fetch_feed,
    iter_feed_rows,
    match_detail_feed_url,
    match_list_feed_url,
    parse_fields,
)
from match_settle import is_finished_status, settle_prediction_row, status_label
from matches_check import parse_match_time
from settings import DeluxSettings


def _adjust_scores(first_home: int, first_away: int, second_home: int, second_away: int) -> Tuple[int, int]:
    first_home_adj = first_home - second_home
    first_away_adj = first_away - second_away
    return first_home_adj + second_home, first_away_adj + second_away


def _ingest_list_feed(index: Dict[str, dict], url: str) -> None:
    try:
        feed = fetch_feed(url)
    except RuntimeError as exc:
        print(f"[!] {exc}")
        return
    for fs_index_name, _fs_index_value, fields in iter_feed_rows(feed):
        if fs_index_name != "AA":
            continue
        data = parse_fields(fields)
        match_id = data.get("AA", "")
        if match_id and match_id not in index:
            index[match_id] = data


def _build_feed_index(sport_id: str, settings: DeluxSettings, days_back: int = 14) -> Dict[str, dict]:
    """Лента за сегодня и прошедшие дни: ночные матчи пропадают из dayzone=0."""
    ms = settings.match_settings
    index: Dict[str, dict] = {}
    for delta in range(max(0, days_back) + 1):
        url = match_list_feed_url(
            int(sport_id),
            settings.dayzone - delta,
            settings.timezone,
            sourcer=ms.sourcer,
            suffix=ms.suffix,
        )
        _ingest_list_feed(index, url)
    return index


def _fetch_match_row(sport_id: str, match_id: str, settings: DeluxSettings) -> Optional[dict]:
    ms = settings.match_settings
    url = match_detail_feed_url(int(sport_id), match_id, sourcer=ms.sourcer)
    try:
        feed = fetch_feed(url, retries=2, timeout=15)
    except RuntimeError:
        return None
    for fs_index_name, _fs_index_value, fields in iter_feed_rows(feed):
        data = parse_fields(fields)
        if (fs_index_name == "AA" and data.get("AA") == match_id) or data.get("AA") == match_id:
            return data
        if data.get("AC") and ("AT" in data or "AG" in data):
            data.setdefault("AA", match_id)
            return data
    return None


def _scores_from_feed(data: dict) -> Tuple[int, int]:
    first_home = int(float(data.get("AT") or data.get("AG") or 0))
    first_away = int(float(data.get("AU") or data.get("AH") or 0))
    second_home = int(float(data.get("BC") or 0))
    second_away = int(float(data.get("BD") or 0))
    return _adjust_scores(first_home, first_away, second_home, second_away)


def _kickoff_due(row, *, min_age_sec: int = 90 * 60) -> bool:
    ts = row["start_ts"] if "start_ts" in row.keys() else None
    try:
        if ts:
            return time.time() > float(ts) + min_age_sec
    except (TypeError, ValueError):
        pass
    dt = parse_match_datetime(row["match_date"] if "match_date" in row.keys() else None)
    if dt is None:
        return True
    return time.time() > dt.timestamp() + min_age_sec


def run_db_check() -> int:
    from db import create_database, get_db_connection

    settings = DeluxSettings.from_env()
    create_database()

    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT m.match_id, m.sport, m.match_status, m.start_ts, m.match_date,
                   m.score_home, m.score_away,
                   sp.strategy_id, sp.prediction, sp.odds, sp.notes, sp.id AS sp_id
            FROM matches m
            LEFT JOIN strategy_predictions sp ON sp.match_id = m.match_id
            WHERE m.match_status NOT IN ('Завершен', 'После овертайма', 'После буллитов')
               OR m.match_status IS NULL
               OR (COALESCE(m.score_home, 0) + COALESCE(m.score_away, 0) > 0
                   AND m.match_status IN ('Не начался', 'Ждем...'))
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
            if not data and _kickoff_due(row):
                data = _fetch_match_row(sport, match_id, settings)
                if data:
                    feeds.setdefault(sport, {})[match_id] = data
            period_text = ""
            minute_text = "90+"
            if not data:
                existing_home = row["score_home"]
                existing_away = row["score_away"]
                if is_finished_status(row["match_status"], existing_home, existing_away):
                    total_home, total_away = int(existing_home), int(existing_away)
                    status_text = "Завершен"
                else:
                    continue
            else:
                total_home, total_away = _scores_from_feed(data)
                status_text = status_label(str(data.get("AC", "")))
                period_text, minute_text = parse_match_time(str(data.get("BX", "") or data.get("CX", "")))

            result = "П1" if total_home > total_away else ("П2" if total_home < total_away else "X")
            finished = is_finished_status(status_text, total_home, total_away)
            if finished and status_text in ("Не начался", "Ждем...", ""):
                status_text = "Завершен"

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
                if finished:
                    coeff = float(row["odds"] or 0) or 1.0
                    notes = row["notes"] if "notes" in row.keys() else None
                    status, profit = settle_prediction_row(
                        str(row["prediction"]),
                        result,
                        total_home,
                        total_away,
                        coeff,
                        notes=notes,
                    )
                    conn.execute(
                        """
                        UPDATE strategy_predictions SET result = ?, profit = ?
                        WHERE id = ?
                        """,
                        (status, profit, row["sp_id"]),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE strategy_predictions SET result = NULL, profit = NULL
                        WHERE id = ?
                        """,
                        (row["sp_id"],),
                    )
            updated += 1

    print(f"[+] Обновлено матчей: {updated}")
    return 0
