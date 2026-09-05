"""Статистика по травмированным / отсутствующим игрокам."""

from __future__ import annotations

import sqlite3
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from db import get_database_path
from favorites_stats.missing_players_api import (
    MissingPlayer,
    fetch_missing_players,
    side_injury_totals,
)
from favorites_stats.repository import FinishedMatch, load_finished_matches
from favorites_stats.settlement import identify_favorite, settle_win
from favorites_stats.sports import sport_label
from favorites_stats.storage import (
    ensure_missing_players_schema,
    load_missing_players,
    matches_without_injury_data,
    row_to_missing_player,
    save_missing_players,
)


def _reason_stats(rows: List[sqlite3.Row]) -> List[dict]:
    counter: Dict[str, int] = defaultdict(int)
    for row in rows:
        reason = (row["reason"] or "—").strip() or "—"
        counter[reason] += 1
    return [{"reason": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))]


def _category_stats(rows: List[sqlite3.Row]) -> Dict[str, int]:
    counter: Dict[str, int] = defaultdict(int)
    for row in rows:
        counter[row["category"] or "other"] += 1
    return dict(sorted(counter.items(), key=lambda x: (-x[1], x[0])))


def fetch_and_store_missing_players(
    match_ids: List[str],
    *,
    db_path: Optional[str] = None,
    delay_sec: float = 0.35,
    limit: int = 0,
) -> dict:
    path = get_database_path(db_path)
    ids = match_ids[:limit] if limit and limit > 0 else match_ids

    conn = sqlite3.connect(path)
    try:
        ensure_missing_players_schema(conn)
        todo = matches_without_injury_data(conn, ids)
    finally:
        conn.close()

    fetched = 0
    saved_rows = 0
    errors: List[dict] = []

    conn = sqlite3.connect(path)
    try:
        ensure_missing_players_schema(conn)
        for idx, match_id in enumerate(todo, start=1):
            batch = fetch_missing_players(match_id)
            if batch.fetch_error:
                errors.append({"match_id": match_id, "error": batch.fetch_error})
            else:
                saved_rows += save_missing_players(conn, batch)
                fetched += 1
            conn.commit()
            if idx < len(todo):
                time.sleep(delay_sec)
    finally:
        conn.close()

    return {
        "requested": len(ids),
        "to_fetch": len(todo),
        "fetched_ok": fetched,
        "rows_saved": saved_rows,
        "errors": errors[:20],
        "api": "https://46.ds.lsapp.eu/pq_graphql?_hash=dmpe2&eventId={match_id}&projectId=46",
    }


def _row_to_missing_player(row: sqlite3.Row) -> MissingPlayer:
    return row_to_missing_player(row)


def _favorite_injury_impact(matches: List[FinishedMatch], by_match: Dict[str, List[MissingPlayer]]) -> dict:
    buckets = {
        "favorite_has_injury": {"bets": 0, "wins": 0, "profit": 0.0},
        "favorite_no_injury": {"bets": 0, "wins": 0, "profit": 0.0},
        "underdog_has_injury": {"bets": 0, "wins": 0, "profit": 0.0},
        "no_lineup_data": {"bets": 0, "wins": 0, "profit": 0.0},
    }

    for match in matches:
        fav = identify_favorite(match.odds.get("1X2_1"), match.odds.get("1X2_2"))
        if not fav:
            continue
        players = by_match.get(match.match_id)
        if not players:
            key = "no_lineup_data"
        else:
            fav_side = "HOME" if fav.side == "home" else "AWAY"
            dog_side = "AWAY" if fav_side == "HOME" else "HOME"
            fav_inj = side_injury_totals(players, fav_side)["confirmed_injuries"]
            dog_inj = side_injury_totals(players, dog_side)["confirmed_injuries"]
            if fav_inj > 0:
                key = "favorite_has_injury"
            elif dog_inj > 0:
                key = "underdog_has_injury"
            else:
                key = "favorite_no_injury"

        won = settle_win(match.score_home, match.score_away, fav.side)
        bucket = buckets[key]
        bucket["bets"] += 1
        if won:
            bucket["wins"] += 1
            bucket["profit"] += fav.win_odds - 1
        else:
            bucket["profit"] -= 1

    out = {}
    for key, b in buckets.items():
        n = b["bets"]
        out[key] = {
            **b,
            "profit": round(b["profit"], 2),
            "winrate_pct": round(b["wins"] / n * 100, 2) if n else None,
            "roi_pct": round(b["profit"] / n * 100, 2) if n else None,
        }
    return out


def fetch_and_store_for_match(match_id: str, *, db_path: Optional[str] = None) -> dict:
    """Загрузить missingPlayers для одного матча и сохранить в БД."""
    path = get_database_path(db_path)
    batch = fetch_missing_players(match_id)
    conn = sqlite3.connect(path)
    try:
        saved = save_missing_players(conn, batch)
        conn.commit()
    finally:
        conn.close()
    return {
        "match_id": match_id,
        "saved": saved,
        "players": len(batch.players),
        "injuries": batch.injury_count,
        "error": batch.fetch_error,
    }


def fetch_injuries_for_matches(
    match_ids: List[str],
    *,
    db_path: Optional[str] = None,
    delay_sec: float = 0.35,
) -> dict:
    """Подгрузка травм для списка матчей (пропуск уже загруженных)."""
    return fetch_and_store_missing_players(
        match_ids,
        db_path=db_path,
        delay_sec=delay_sec,
        limit=0,
    )


def build_injuries_report(
    db_path: Optional[str] = None,
    *,
    fetch: bool = False,
    fetch_limit: int = 50,
    finished_matches: Optional[List[FinishedMatch]] = None,
) -> Dict[str, Any]:
    path = get_database_path(db_path)

    fetch_summary = None
    if fetch:
        if finished_matches is None:
            finished_matches = load_finished_matches(path, favorite_leagues_only=False)

        conn = sqlite3.connect(path)
        try:
            queue_ids = [
                row[0]
                for row in conn.execute(
                    "SELECT match_id FROM match_queue ORDER BY loaded_at DESC"
                ).fetchall()
            ]
        finally:
            conn.close()

        finished_ids = [m.match_id for m in (finished_matches or [])]
        ordered = list(dict.fromkeys(queue_ids + finished_ids))
        fetch_summary = fetch_and_store_missing_players(
            ordered,
            db_path=path,
            limit=fetch_limit,
        )

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_missing_players_schema(conn)
        rows = conn.execute(
            """
            SELECT match_id, side, player_id, player_name, list_name, team_name,
                   participant_url, team_logos, event_participant_id, source_bucket,
                   reason, category, is_unsure, raw_json
            FROM match_missing_players
            WHERE player_id != '__none__'
            """
        ).fetchall()
        sport_map = {
            row["match_id"]: int(row["sport"] or 1)
            for row in conn.execute("SELECT match_id, sport FROM matches").fetchall()
        }
    finally:
        conn.close()

    if not rows:
        return {
            "status": "no_data",
            "message": (
                "В БД нет сохранённых данных о травмах. "
                "Источник: Flashscore pq_graphql (_hash=dmpe2). "
                "Запустите с --fetch-injuries для загрузки."
            ),
            "database": path,
            "available": False,
            "api_example": (
                "https://46.ds.lsapp.eu/pq_graphql?_hash=dmpe2&eventId=27MtCUO7&projectId=46"
            ),
            "fetch": fetch_summary,
        }

    by_match_players: Dict[str, List[MissingPlayer]] = defaultdict(list)
    by_sport: Dict[int, dict] = defaultdict(lambda: {"players": 0, "injuries": 0, "matches": set()})

    for row in rows:
        if row["category"] == "none" or row["player_id"] == "__none__":
            continue
        player = _row_to_missing_player(row)
        by_match_players[row["match_id"]].append(player)
        sport_id = sport_map.get(row["match_id"], 0)
        bucket = by_sport[sport_id]
        bucket["players"] += 1
        bucket["matches"].add(row["match_id"])
        if player.category == "injury":
            bucket["injuries"] += 1

    sport_breakdown = []
    for sport_id, data in sorted(by_sport.items()):
        sport_breakdown.append(
            {
                "sport_id": sport_id,
                "sport_name": sport_label(sport_id) if sport_id else "Неизвестно",
                "matches_with_data": len(data["matches"]),
                "missing_players": data["players"],
                "injury_records": data["injuries"],
            }
        )

    if finished_matches is None:
        finished_matches = load_finished_matches(path, favorite_leagues_only=False)

    impact = _favorite_injury_impact(finished_matches, by_match_players)

    matches_with_injuries = sum(
        1
        for players in by_match_players.values()
        if any(p.category == "injury" and not p.is_unsure for p in players)
    )

    return {
        "status": "ok",
        "message": f"Загружено записей об отсутствующих игроках: {len(rows)}",
        "database": path,
        "available": True,
        "api": "https://46.ds.lsapp.eu/pq_graphql?_hash=dmpe2&eventId={match_id}&projectId=46",
        "matches_with_data": len(by_match_players),
        "matches_with_confirmed_injuries": matches_with_injuries,
        "total_records": len(rows),
        "by_category": _category_stats(rows),
        "top_reasons": _reason_stats(rows)[:15],
        "by_sport": sport_breakdown,
        "favorite_win_impact": impact,
        "fetch": fetch_summary,
    }
