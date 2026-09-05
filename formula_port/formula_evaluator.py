"""Интерпретатор формул Excel (подмножество функций DeluX)."""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from openpyxl.utils import column_index_from_string, get_column_letter
from formula_port.excel_functions import FUNCTIONS, NA_ERROR, _num
from formula_port.refs import col_row, parse_formula_refs

Token = Tuple[str, Any]


class FormulaError(Exception):
    pass


def _tokenize(formula: str) -> List[Token]:
    s = formula.strip()
    if s.startswith("="):
        s = s[1:]
    tokens: List[Token] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "#":
            j = i
            while j < len(s) and s[j] not in " ),+-*/&<>=;":
                j += 1
            tokens.append(("ERROR", s[i:j]))
            i = j
            continue
        if ch == '"':
            j = i + 1
            parts = []
            while j < len(s):
                if s[j] == '"':
                    if j + 1 < len(s) and s[j + 1] == '"':
                        parts.append('"')
                        j += 2
                    else:
                        break
                else:
                    parts.append(s[j])
                    j += 1
            tokens.append(("STRING", "".join(parts)))
            i = j + 1
            continue
        if ch in "+-*/^&":
            tokens.append(("OP", ch))
            i += 1
            continue
        if ch in "<>=":
            if i + 1 < len(s) and s[i : i + 2] in ("<=", ">=", "<>"):
                tokens.append(("OP", s[i : i + 2]))
                i += 2
            else:
                tokens.append(("OP", ch))
                i += 1
            continue
        if ch in ",;()":
            tokens.append(("PUNC", ch))
            i += 1
            continue
        if ch == "{":
            j = s.find("}", i)
            inner = s[i + 1 : j] if j > i else ""
            parts: List[str] = []
            buf = ""
            in_str = False
            for c in inner:
                if c == '"':
                    in_str = not in_str
                    continue
                # ; = новая строка, , = новая колонка — для VLOOKUP flatten по парам
                if c in ",;" and not in_str:
                    parts.append(buf.strip())
                    buf = ""
                else:
                    buf += c
            parts.append(buf.strip())
            tokens.append(("ARRAY", parts))
            i = j + 1 if j > i else i + 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < len(s) and s[i + 1].isdigit()):
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ".":
                j += 1
                while j < len(s) and s[j].isdigit():
                    j += 1
            elif j < len(s) and s[j] == "," and j + 1 < len(s) and s[j + 1].isdigit():
                j += 1
                while j < len(s) and s[j].isdigit():
                    j += 1
            num_s = s[i:j].replace(",", ".")
            try:
                val = float(num_s)
            except ValueError:
                tokens.append(("STRING", s[i:j]))
                i = j
                continue
            if j < len(s) and s[j] == "%":
                val /= 100.0
                j += 1
            tokens.append(("NUMBER", val))
            i = j
            continue
        m = re.match(
            r"(?:'([^']+)'|([A-Za-z\u0410-\u042f\u0430-\u044f\u0401\u04510-9 _]+))!#REF!",
            s[i:],
            re.I,
        )
        if m:
            tokens.append(("ERROR", "#REF!"))
            i += len(m.group(0))
            continue
        m = re.match(
            r"(?:'([^']+)'|([A-Za-z\u0410-\u042f\u0430-\u044f\u0401\u04510-9 _]+))!"
            r"(\$?[A-Za-z]{1,3}\$?\d*(?::\$?[A-Za-z]{1,3}\$?\d*)?)",
            s[i:],
            re.I,
        )
        if m:
            tokens.append(("REF", m.group(0)))
            i += len(m.group(0))
            continue
        # Column range A:A / $A:$C (no row numbers)
        m = re.match(r"\$?[A-Za-z]{1,3}:\$?[A-Za-z]{1,3}", s[i:], re.I)
        if m:
            tokens.append(("REF", m.group(0)))
            i += len(m.group(0))
            continue
        # Cell or A1:B2 — row digits required on at least one side
        m = re.match(
            r"\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?",
            s[i:],
            re.I,
        )
        if m:
            tokens.append(("REF", m.group(0)))
            i += len(m.group(0))
            continue
        m = re.match(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_.]*", s[i:])
        if m:
            word = m.group(0)
            upper = word.upper()
            if upper in ("TRUE", "FALSE"):
                tokens.append(("BOOL", upper == "TRUE"))
            else:
                tokens.append(("NAME", upper))
            i += len(word)
            continue
        raise FormulaError(f"Unexpected char at {i}: {s[i:i+10]!r}")
    return tokens


class Evaluator:
    def __init__(self, store: CellStore, default_sheet: str):
        self.store = store
        self.default_sheet = default_sheet
        self._eval_stack: set = set()

    def eval_cell(self, sheet: str, addr: str) -> Any:
        key = self.store.key(sheet, addr)
        if key in self._eval_stack:
            return NA_ERROR
        formula = self.store.get_formula(sheet, addr)
        if formula is None:
            cached = self.store.get(sheet, addr)
            return cached if cached is not None else 0
        if key in self.store._values and key not in self._eval_stack:
            return self.store._values[key]
        self._eval_stack.add(key)
        prev_addr = getattr(self, "_current_addr", None)
        self._current_addr = addr
        try:
            val = self.eval_formula(formula, sheet)
            self.store.set_value(sheet, addr, val)
            return val
        except (FormulaError, ValueError, TypeError, ZeroDivisionError):
            self.store.set_value(sheet, addr, "#VALUE!")
            return "#VALUE!"
        finally:
            self._current_addr = prev_addr
            self._eval_stack.discard(key)

    def eval_formula(self, formula: str, default_sheet: str) -> Any:
        tokens = _tokenize(formula)
        result, _ = self._parse_expr(tokens, 0, default_sheet)
        return result

    def _resolve_ref(self, token: str, default_sheet: str) -> Any:
        token = token.replace("$", "")
        if "!" in token:
            sheet_part, addr_part = token.split("!", 1)
            sheet = sheet_part.strip("'")
        else:
            sheet = default_sheet
            addr_part = token
        if ":" in addr_part:
            a, b = addr_part.split(":", 1)
            if re.match(r"^[A-Za-z]+$", a) and re.match(r"^[A-Za-z]+$", b):
                c1 = column_index_from_string(a.upper())
                c2 = column_index_from_string(b.upper())
                if c1 > c2:
                    c1, c2 = c2, c1
                if c1 == c2:
                    max_r = min(max(self.store.used_rows(sheet), 2), 250)
                    letter = get_column_letter(c1)
                    rows = [self._cell_value(sheet, f"{letter}{r}") for r in range(1, max_r + 1)]
                else:
                    max_r = min(max(self.store.used_rows(sheet), 2), 250)
                    rows = []
                    for r in range(1, max_r + 1):
                        rows.append(
                            [
                                self._cell_value(sheet, f"{get_column_letter(c)}{r}")
                                for c in range(c1, c2 + 1)
                            ]
                        )
                return rows
            c1, r1, c2, r2 = self._split_range(addr_part)
            rows = []
            for r in range(r1, r2 + 1):
                row = []
                for c in range(c1, c2 + 1):
                    addr = f"{get_column_letter(c)}{r}"
                    row.append(self._cell_value(sheet, addr))
                rows.append(row)
            return rows
        return self._cell_value(sheet, addr_part)

    def _cell_value(self, sheet: str, addr: str) -> Any:
        if self.store.has_formula(sheet, addr):
            return self.eval_cell(sheet, addr)
        val = self.store.get(sheet, addr)
        return val if val is not None else 0

    def _split_range(self, addr: str) -> Tuple[int, int, int, int]:
        a, b = addr.split(":")
        c1, r1 = col_row(a)
        c2, r2 = col_row(b)
        if c1 > c2:
            c1, c2 = c2, c1
        if r1 > r2:
            r1, r2 = r2, r1
        return c1, r1, c2, r2

    def _parse_expr(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        return self._parse_compare(tokens, pos, sheet)

    def _parse_compare(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        left, pos = self._parse_concat(tokens, pos, sheet)
        while pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] in ("=", "<>", "<", ">", "<=", ">="):
            op = tokens[pos][1]
            pos += 1
            right, pos = self._parse_concat(tokens, pos, sheet)
            left = self._compare(op, left, right)
        return left, pos

    def _coerce_number(self, v: Any) -> Optional[float]:
        """Число или None, если значение — нечисловой текст (Excel type-aware =)."""
        if v is None or v == "":
            return 0.0
        if isinstance(v, bool):
            return float(v)
        if isinstance(v, (int, float)):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return 0.0
            return float(v)
        if isinstance(v, str):
            if v.startswith("#"):
                return None
            s = v.strip().replace(",", ".")
            if s.endswith("%"):
                try:
                    return float(s[:-1]) / 100.0
                except ValueError:
                    return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    def _excel_equal(self, a: Any, b: Any) -> bool:
        """Excel '=': числа сравниваются как числа, текст — как текст; число≠текст."""
        if self._is_error(a) or self._is_error(b):
            return False
        an = self._coerce_number(a)
        bn = self._coerce_number(b)
        a_is_text = an is None
        b_is_text = bn is None
        if not a_is_text and not b_is_text:
            return an == bn
        if a_is_text and b_is_text:
            return str(a).strip().lower() == str(b).strip().lower()
        return False

    def _compare(self, op: str, a: Any, b: Any) -> bool:
        if op == "=":
            return self._excel_equal(a, b)
        if op == "<>":
            return not self._excel_equal(a, b)
        # Неравенства: как Excel — нечисловой текст → 0
        av, bv = _num(a), _num(b)
        if op == "<":
            return av < bv
        if op == ">":
            return av > bv
        if op == "<=":
            return av <= bv
        if op == ">=":
            return av >= bv
        return False

    def _excel_text(self, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return str(v)
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            # Локаль книги RU: 7.5 → «7,5» при &
            return str(v).replace(".", ",")
        if isinstance(v, int):
            return str(v)
        return str(v)

    def _parse_concat(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        left, pos = self._parse_add(tokens, pos, sheet)
        while pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] == "&":
            pos += 1
            right, pos = self._parse_add(tokens, pos, sheet)
            left = self._excel_text(left) + self._excel_text(right)
        return left, pos

    def _is_error(self, v: Any) -> bool:
        return isinstance(v, str) and v.startswith("#")

    def _parse_add(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        left, pos = self._parse_mul(tokens, pos, sheet)
        while pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] in ("+", "-"):
            op = tokens[pos][1]
            pos += 1
            right, pos = self._parse_mul(tokens, pos, sheet)
            if self._is_error(left):
                continue
            if self._is_error(right):
                left = right
                continue
            if op == "+":
                left = _num(left) + _num(right)
            else:
                left = _num(left) - _num(right)
        return left, pos

    def _parse_mul(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        left, pos = self._parse_pow(tokens, pos, sheet)
        while pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] in ("*", "/"):
            op = tokens[pos][1]
            pos += 1
            right, pos = self._parse_pow(tokens, pos, sheet)
            if self._is_error(left):
                continue
            if self._is_error(right):
                left = right
                continue
            # Нечисловые строки в арифметике → #VALUE! (Excel), не 0.
            if isinstance(left, str) and left != "" and not self._is_error(left):
                try:
                    float(str(left).replace(",", ".").rstrip("%"))
                except ValueError:
                    left = "#VALUE!"
                    continue
            if isinstance(right, str) and right != "" and not self._is_error(right):
                try:
                    float(str(right).replace(",", ".").rstrip("%"))
                except ValueError:
                    left = "#VALUE!"
                    continue
            if op == "*":
                left = _num(left) * _num(right)
            else:
                rv = _num(right)
                left = _num(left) / rv if rv else "#DIV/0!"
        return left, pos

    def _parse_pow(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        left, pos = self._parse_unary(tokens, pos, sheet)
        while pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] == "^":
            pos += 1
            right, pos = self._parse_unary(tokens, pos, sheet)
            if self._is_error(left):
                continue
            if self._is_error(right):
                left = right
                continue
            left = _num(left) ** _num(right)
        return left, pos

    def _parse_unary(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        if pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] == "-":
            pos += 1
            val, pos = self._parse_unary(tokens, pos, sheet)
            return -_num(val), pos
        if pos < len(tokens) and tokens[pos][0] == "OP" and tokens[pos][1] == "+":
            pos += 1
        return self._parse_primary(tokens, pos, sheet)

    def _parse_primary(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        if pos >= len(tokens):
            return 0, pos
        kind, val = tokens[pos]
        if kind == "ERROR":
            return val, pos + 1
        if kind == "NUMBER":
            return val, pos + 1
        if kind == "STRING":
            return val, pos + 1
        if kind == "BOOL":
            return val, pos + 1
        if kind == "ARRAY":
            return val, pos + 1
        if kind == "REF":
            return self._resolve_ref(val, sheet), pos + 1
        if kind == "NAME":
            return self._parse_call(tokens, pos, sheet)
        if kind == "PUNC" and val == "(":
            inner, pos = self._parse_expr(tokens, pos + 1, sheet)
            if pos < len(tokens) and tokens[pos] == ("PUNC", ")"):
                pos += 1
            return inner, pos
        raise FormulaError(f"Unexpected token {kind}:{val}")

    def _parse_call(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        name = tokens[pos][1]
        pos += 1
        if pos >= len(tokens) or tokens[pos] != ("PUNC", "("):
            return name, pos
        pos += 1
        if name == "OFFSET":
            return self._parse_offset(tokens, pos, sheet)
        args: List[Any] = []
        if pos < len(tokens) and tokens[pos] == ("PUNC", ")"):
            return self._call_fn(name, args), pos + 1
        while True:
            arg, pos = self._parse_expr(tokens, pos, sheet)
            args.append(arg)
            if pos < len(tokens) and tokens[pos] == ("PUNC", ","):
                pos += 1
                continue
            if pos < len(tokens) and tokens[pos] == ("PUNC", ";"):
                pos += 1
                continue
            break
        if pos < len(tokens) and tokens[pos] == ("PUNC", ")"):
            pos += 1
        return self._call_fn(name, args), pos

    def _parse_offset(self, tokens: List[Token], pos: int, sheet: str) -> Tuple[Any, int]:
        """OFFSET(ref, rows, cols, [height], [width]) — ref must stay an address."""
        if pos >= len(tokens):
            return NA_ERROR, pos
        if tokens[pos][0] == "REF":
            ref_token = tokens[pos][1]
            pos += 1
        else:
            # fallback: evaluate then fail soft
            _ignored, pos = self._parse_expr(tokens, pos, sheet)
            ref_token = None
        if pos < len(tokens) and tokens[pos][0] == "PUNC" and tokens[pos][1] in (",", ";"):
            pos += 1
        args: List[Any] = []
        while pos < len(tokens) and tokens[pos] != ("PUNC", ")"):
            if tokens[pos][0] == "PUNC" and tokens[pos][1] in (",", ";"):
                pos += 1
                continue
            arg, pos = self._parse_expr(tokens, pos, sheet)
            args.append(arg)
        if pos < len(tokens) and tokens[pos] == ("PUNC", ")"):
            pos += 1
        if ref_token is None or len(args) < 2:
            return NA_ERROR, pos
        rows_off = int(_num(args[0]))
        cols_off = int(_num(args[1]))
        height = int(_num(args[2])) if len(args) > 2 else 1
        width = int(_num(args[3])) if len(args) > 3 else 1
        ref = ref_token.replace("$", "")
        if "!" in ref:
            sheet_part, addr_part = ref.split("!", 1)
            ref_sheet = sheet_part.strip("'")
        else:
            ref_sheet = sheet
            addr_part = ref
        if ":" in addr_part:
            addr_part = addr_part.split(":", 1)[0]
        c0, r0 = col_row(addr_part)
        c1 = c0 + cols_off
        r1 = r0 + rows_off
        if height == 1 and width == 1:
            return self._cell_value(ref_sheet, f"{get_column_letter(c1)}{r1}"), pos
        block = []
        for r in range(r1, r1 + height):
            row = []
            for c in range(c1, c1 + width):
                row.append(self._cell_value(ref_sheet, f"{get_column_letter(c)}{r}"))
            block.append(row[0] if width == 1 else row)
        return block if height > 1 else block[0], pos

    def _call_fn(self, name: str, args: List[Any]) -> Any:
        if name == "COLUMN":
            if args:
                ref = args[0]
                # Range/list → first column not supported; treat as 1
                return 1
            addr = getattr(self, "_current_addr", "A1") or "A1"
            letters = "".join(ch for ch in addr if ch.isalpha())
            return column_index_from_string(letters.upper()) if letters else 1
        if name == "ROW":
            if args:
                return 1
            addr = getattr(self, "_current_addr", "A1") or "A1"
            digits = "".join(ch for ch in addr if ch.isdigit())
            return int(digits) if digits else 1
        fn = FUNCTIONS.get(name)
        if fn is None:
            fn = FUNCTIONS.get(name.replace("_XLFN.", ""))
        if fn is None:
            return NA_ERROR
        try:
            return fn(*args)
        except Exception:
            return NA_ERROR


def topological_sort(store: CellStore, sheets: List[str]) -> List[Tuple[str, str]]:
    sheet_set = set(sheets)
    cells = [(s, a) for s, a in store.all_formula_keys() if s in sheet_set]
    deps: Dict[str, set] = {}
    for sheet, addr in cells:
        key = store.key(sheet, addr)
        formula = store.get_formula(sheet, addr) or ""
        refs = parse_formula_refs(formula, default_sheet=sheet)
        dep_keys = set()
        for r in refs:
            if r.sheet in sheet_set or store.has_formula(r.sheet, r.a1()):
                dep_keys.add(r.key())
        deps[key] = dep_keys

    ordered: List[Tuple[str, str]] = []
    done = set()
    remaining = {store.key(s, a): (s, a) for s, a in cells}
    guard = 0
    while remaining and guard < len(remaining) * 3 + 10:
        guard += 1
        progressed = False
        for key, (sheet, addr) in list(remaining.items()):
            if deps.get(key, set()).issubset(done):
                ordered.append((sheet, addr))
                done.add(key)
                del remaining[key]
                progressed = True
        if not progressed:
            for key, pair in remaining.items():
                ordered.append(pair)
            break
    return ordered
