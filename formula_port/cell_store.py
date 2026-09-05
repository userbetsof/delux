"""Хранилище значений ячеек (sheet!A1)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from openpyxl.utils import get_column_letter

from formula_port.refs import CellRef, col_row, expand_ref, iter_range


class CellStore:
    def __init__(self):
        self._values: Dict[str, Any] = {}
        self._formulas: Dict[str, str] = {}

    def key(self, sheet: str, addr: str) -> str:
        return f"{sheet}!{addr.replace('$', '').upper()}"

    def set_value(self, sheet: str, addr: str, value: Any) -> None:
        self._values[self.key(sheet, addr)] = value

    def set_formula(self, sheet: str, addr: str, formula: str) -> None:
        self._formulas[self.key(sheet, addr)] = formula

    def get(self, sheet: str, addr: str) -> Any:
        k = self.key(sheet, addr)
        if k in self._values:
            return self._values[k]
        return None

    def has_formula(self, sheet: str, addr: str) -> bool:
        return self.key(sheet, addr) in self._formulas

    def get_formula(self, sheet: str, addr: str) -> Optional[str]:
        return self._formulas.get(self.key(sheet, addr))

    def bulk_set_formulas(self, sheet: str, mapping: Dict[str, str]) -> None:
        for addr, formula in mapping.items():
            self.set_formula(sheet, addr, formula)

    def bulk_set_values(self, sheet: str, mapping: Dict[str, Any]) -> None:
        for addr, value in mapping.items():
            self.set_value(sheet, addr, value)

    def load_static(self, entries: Dict[str, Any]) -> None:
        self._values.update(entries)

    def get_range(self, sheet: str, start: str, end: str) -> List[List[Any]]:
        sc, sr = col_row(start)
        ec, er = col_row(end)
        rows: List[List[Any]] = []
        for r in range(sr, er + 1):
            row_vals = []
            for c in range(sc, ec + 1):
                addr = f"{get_column_letter(c)}{r}"
                row_vals.append(self.get(sheet, addr))
            rows.append(row_vals)
        return rows

    def set_range(self, sheet: str, start_row: int, start_col: int, rows: List[List[Any]]) -> None:
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                addr = f"{get_column_letter(start_col + ci)}{start_row + ri}"
                self.set_value(sheet, addr, val)

    def all_formula_keys(self) -> List[Tuple[str, str]]:
        out = []
        for k, f in self._formulas.items():
            sheet, addr = k.split("!", 1)
            out.append((sheet, addr))
        return out

    def ref_value(self, ref: CellRef) -> Any:
        return self.get(ref.sheet, ref.a1())

    def used_rows(self, sheet: str) -> int:
        if not hasattr(self, "_used_rows_cache"):
            self._used_rows_cache = {}
        if sheet in self._used_rows_cache:
            return self._used_rows_cache[sheet]
        prefix = f"{sheet}!"
        mx = 1
        for mapping in (self._values, self._formulas):
            for k in mapping:
                if not k.startswith(prefix):
                    continue
                addr = k.split("!", 1)[1]
                m = re.search(r"(\d+)$", addr)
                if m:
                    mx = max(mx, int(m.group(1)))
        self._used_rows_cache[sheet] = mx
        return mx

    def column_values(self, sheet: str, col: int, col_end: int | None = None) -> list:
        """Values in columns col..col_end for populated rows only (full-column refs)."""
        from openpyxl.utils import column_index_from_string, get_column_letter

        c2 = col_end or col
        prefix = f"{sheet}!"
        rows_seen = set()
        for mapping in (self._values, self._formulas):
            for k in mapping:
                if not k.startswith(prefix):
                    continue
                addr = k.split("!", 1)[1]
                m = re.match(r"^([A-Za-z]+)(\d+)$", addr)
                if not m:
                    continue
                ci = column_index_from_string(m.group(1))
                if col <= ci <= c2:
                    rows_seen.add(int(m.group(2)))
        if not rows_seen:
            return []
        out = []
        for r in range(min(rows_seen), max(rows_seen) + 1):
            if c2 == col:
                out.append(self.get(sheet, f"{get_column_letter(col)}{r}"))
            else:
                out.append(
                    [self.get(sheet, f"{get_column_letter(c)}{r}") for c in range(col, c2 + 1)]
                )
        return out
        if not hasattr(self, "_used_rows_cache"):
            return
        if sheet is None:
            self._used_rows_cache.clear()
        else:
            self._used_rows_cache.pop(sheet, None)
