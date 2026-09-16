from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

from db import get_database_path


class DatabaseCatalog:
    """Полный read-only доступ ML-слоя к SQLite и манифест её схемы."""

    def __init__(self, path: str | None = None):
        self.path = Path(get_database_path(path)).resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        uri = f"file:{self.path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        try:
            yield conn
        finally:
            conn.close()

    def tables(self) -> List[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def columns(self, table: str) -> List[Dict[str, Any]]:
        if table not in self.tables():
            raise ValueError(f"Unknown table: {table}")
        escaped = table.replace('"', '""')
        with self.connect() as conn:
            rows = conn.execute(f'PRAGMA table_info("{escaped}")').fetchall()
        return [dict(row) for row in rows]

    def manifest(self) -> Dict[str, Any]:
        return {
            "database": str(self.path),
            "tables": {table: self.columns(table) for table in self.tables()},
        }

    def schema_hash(self) -> str:
        raw = json.dumps(self.manifest()["tables"], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        statement = sql.lstrip().lower()
        if not (statement.startswith("select") or statement.startswith("with")):
            raise ValueError("ML database access is read-only; only SELECT/WITH is allowed")
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]

    def count_rows(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for table in self.tables():
            escaped = table.replace('"', '""')
            rows = self.query(f'SELECT COUNT(*) AS count FROM "{escaped}"')
            result[table] = int(rows[0]["count"]) if rows else 0
        return result

