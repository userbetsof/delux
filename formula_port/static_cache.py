"""Кэш статических значений из data/lookups.db."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "lookups.db"


class StaticCache:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DEFAULT_DB)

    def exists(self) -> bool:
        return self.db_path.is_file()

    def load_all(self) -> Dict[str, Any]:
        if not self.exists():
            return {}
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT cell_key, value_text, value_num FROM lookup_values")
        out: Dict[str, Any] = {}
        for key, text, num in cur.fetchall():
            if num is not None:
                out[key] = num
            elif text is not None:
                if text in ("True", "False"):
                    out[key] = text == "True"
                else:
                    try:
                        if "." in text or "e" in text.lower():
                            out[key] = float(text)
                        else:
                            out[key] = int(text)
                    except ValueError:
                        out[key] = text
            else:
                out[key] = None
        conn.close()
        return out

    def apply_to_store(self, store) -> int:
        values = self.load_all()
        store.load_static(values)
        return len(values)

    @staticmethod
    def cell_key(sheet: str, addr: str) -> str:
        return f"{sheet}!{addr.replace('$', '').upper()}"

    def get(self, sheet: str, addr: str, default: Any = None) -> Any:
        values = self.load_all()
        return values.get(self.cell_key(sheet, addr), default)


def load_formula_graph() -> dict:
    path = ROOT / "data" / "formula_graph.json"
    if not path.exists():
        raise FileNotFoundError(f"Run scripts/trace_dependencies.py first: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
