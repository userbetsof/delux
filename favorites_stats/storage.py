"""Хранение отсутствующих игроков в matches.db."""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable, List, Set

from favorites_stats.missing_players_api import MatchMissingPlayers, MissingPlayer

_EXTRA_COLUMNS = (
    ("list_name", "TEXT"),
    ("participant_url", "TEXT"),
    ("team_logos", "TEXT"),
    ("event_participant_id", "TEXT"),
    ("source_bucket", "TEXT"),
    ("raw_json", "TEXT"),
)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def ensure_missing_players_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS match_missing_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id VARCHAR(8) NOT NULL,
            side VARCHAR(8) NOT NULL,
            player_id VARCHAR(32) NOT NULL DEFAULT '',
            player_name TEXT,
            list_name TEXT,
            team_name TEXT,
            participant_url TEXT,
            team_logos TEXT,
            event_participant_id TEXT,
            source_bucket TEXT,
            reason TEXT,
            category TEXT,
            is_unsure INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(match_id, side, player_id, reason, is_unsure)
        )
        """
    )
    existing = _table_columns(conn, "match_missing_players")
    for name, col_type in _EXTRA_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE match_missing_players ADD COLUMN {name} {col_type}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missing_players_match ON match_missing_players(match_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missing_players_category ON match_missing_players(category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_missing_players_player ON match_missing_players(player_id)"
    )


def _player_row_values(player: MissingPlayer) -> tuple:
    logos_json = json.dumps(player.team_logos, ensure_ascii=False) if player.team_logos else ""
    return (
        player.match_id,
        player.side,
        player.player_id,
        player.player_name,
        player.list_name,
        player.team_name,
        player.participant_url,
        logos_json,
        player.event_participant_id,
        player.source_bucket,
        player.reason,
        player.category,
        1 if player.is_unsure else 0,
        player.raw_json,
    )


def save_missing_players(conn: sqlite3.Connection, batch: MatchMissingPlayers) -> int:
    ensure_missing_players_schema(conn)
    if batch.fetch_error:
        return 0
    conn.execute("DELETE FROM match_missing_players WHERE match_id = ?", (batch.match_id,))
    if not batch.players:
        conn.execute(
            """
            INSERT OR REPLACE INTO match_missing_players
                (match_id, side, player_id, player_name, list_name, team_name,
                 participant_url, team_logos, event_participant_id, source_bucket,
                 reason, category, is_unsure, raw_json, fetched_at)
            VALUES (?, '', '__none__', '', '', '', '', '', '', '', 'нет данных', 'none', 0, '', datetime('now'))
            """,
            (batch.match_id,),
        )
        return 1

    insert_sql = """
        INSERT OR REPLACE INTO match_missing_players
            (match_id, side, player_id, player_name, list_name, team_name,
             participant_url, team_logos, event_participant_id, source_bucket,
             reason, category, is_unsure, raw_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """
    saved = 0
    for player in batch.players:
        conn.execute(insert_sql, _player_row_values(player))
        saved += 1
    return saved


def row_to_missing_player(row: sqlite3.Row) -> MissingPlayer:
    return _row_to_missing_player(row)


def _row_to_missing_player(row: sqlite3.Row) -> MissingPlayer:
    logos_raw = row["team_logos"] if "team_logos" in row.keys() else ""
    logos: list = []
    if logos_raw:
        try:
            logos = json.loads(logos_raw)
        except (TypeError, json.JSONDecodeError):
            logos = []

    keys = row.keys()
    return MissingPlayer(
        match_id=row["match_id"],
        side=row["side"],
        player_id=row["player_id"] or "",
        player_name=row["player_name"] or "",
        list_name=(row["list_name"] or "") if "list_name" in keys else "",
        team_name=row["team_name"] or "",
        participant_url=(row["participant_url"] or "") if "participant_url" in keys else "",
        team_logos=logos,
        reason=row["reason"] or "",
        category=row["category"] or "other",
        is_unsure=bool(row["is_unsure"]),
        event_participant_id=(row["event_participant_id"] or "") if "event_participant_id" in keys else "",
        source_bucket=(row["source_bucket"] or "") if "source_bucket" in keys else "",
        raw_json=(row["raw_json"] or "") if "raw_json" in keys else "",
    )


def load_missing_players(conn: sqlite3.Connection, match_id: str) -> List[MissingPlayer]:
    ensure_missing_players_schema(conn)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT match_id, side, player_id, player_name, list_name, team_name,
               participant_url, team_logos, event_participant_id, source_bucket,
               reason, category, is_unsure, raw_json
        FROM match_missing_players
        WHERE match_id = ? AND player_id != '__none__'
        ORDER BY side, is_unsure, player_name
        """,
        (match_id,),
    ).fetchall()
    return [_row_to_missing_player(row) for row in rows]


def load_missing_players_dicts(conn: sqlite3.Connection, match_id: str) -> List[dict]:
    return [p.to_dict() for p in load_missing_players(conn, match_id)]


def matches_without_injury_data(conn: sqlite3.Connection, match_ids: Iterable[str]) -> List[str]:
    ensure_missing_players_schema(conn)
    ids = list(match_ids)
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    have = {
        row[0]
        for row in conn.execute(
            f"SELECT DISTINCT match_id FROM match_missing_players WHERE match_id IN ({placeholders})",
            ids,
        ).fetchall()
    }
    return [mid for mid in ids if mid not in have]


def distinct_match_ids_with_data(conn: sqlite3.Connection) -> Set[str]:
    ensure_missing_players_schema(conn)
    return {row[0] for row in conn.execute("SELECT DISTINCT match_id FROM match_missing_players").fetchall()}
