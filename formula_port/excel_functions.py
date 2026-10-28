"""Excel-совместимые функции для формульного движка."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, List, Optional, Sequence, Union

Number = Union[int, float]
Value = Any

EXCEL_ERROR = "#VALUE!"
NA_ERROR = "#N/A"
DIV0_ERROR = "#DIV/0!"


def _num(v: Value, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        if s.endswith("%"):
            try:
                return float(s[:-1]) / 100.0
            except ValueError:
                return default
        try:
            return float(s)
        except ValueError:
            return default
    return default


def _flatten(args: Sequence) -> List[Value]:
    out: List[Value] = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out.extend(_flatten(a))
        else:
            out.append(a)
    return out


def _is_excel_error(v: Value) -> bool:
    return isinstance(v, str) and v.startswith("#")


def _nums(args: Sequence) -> List[float]:
    """Числа для SUM/AVERAGE/MAX: пустые и ошибки Excel пропускаются."""
    out: List[float] = []
    for x in _flatten(args):
        if x is None or x == "" or _is_excel_error(x):
            continue
        if isinstance(x, str):
            s = x.strip().replace(",", ".")
            if not s:
                continue
            try:
                if s.endswith("%"):
                    out.append(float(s[:-1]) / 100.0)
                else:
                    out.append(float(s))
            except ValueError:
                continue
        elif isinstance(x, bool):
            out.append(float(x))
        elif isinstance(x, (int, float)):
            if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
                continue
            out.append(float(x))
    return out


def IF(condition: Value, true_val: Value, false_val: Value = False) -> Value:
    if isinstance(condition, str) and condition.startswith("#"):
        return condition
    return true_val if _excel_truthy(condition) else false_val


def IFERROR(value: Value, fallback: Value) -> Value:
    if value is None:
        return fallback
    if isinstance(value, str) and value.startswith("#"):
        return fallback
    return value


def _excel_truthy(v: Value) -> bool:
    """Истина в логике Excel IF/AND/OR (bool False ≠ «пропуск»)."""
    if isinstance(v, str) and v.startswith("#"):
        return False
    if v is None or v == "":
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


def AND(*args: Value) -> bool:
    vals = _flatten(args)
    if not vals:
        return False
    return all(_excel_truthy(v) for v in vals)


def OR(*args: Value) -> bool:
    vals = _flatten(args)
    return any(_excel_truthy(v) for v in vals)


def NOT(v: Value) -> bool:
    return not _excel_truthy(v)


def ISNUMBER(v: Value) -> bool:
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.replace(",", "."))
            return True
        except ValueError:
            return False
    return False


def ISERROR(v: Value) -> bool:
    return isinstance(v, str) and v.startswith("#")


def ISEVEN(v: Value) -> bool:
    return int(_num(v)) % 2 == 0


def ROUNDDOWN(v: Value, digits: int = 0) -> float:
    factor = 10 ** int(digits)
    return math.trunc(_num(v) * factor) / factor


def ROUNDUP(v: Value, digits: int = 0) -> float:
    x = _num(v)
    factor = 10 ** int(digits)
    scaled = x * factor
    if x >= 0:
        return math.ceil(scaled) / factor
    return math.floor(scaled) / factor


def _criteria_target(raw: str) -> Value:
    s = raw.strip()
    if s.endswith("%"):
        try:
            return float(s[:-1].replace(",", ".")) / 100.0
        except ValueError:
            return s
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


def match_criteria(value: Value, criteria: Value) -> bool:
    if isinstance(value, str) and value.startswith("#"):
        return False
    crit = str(criteria).strip()
    if crit.endswith("%") and not re.match(r"^(<=|>=|<>|<|>|=)", crit):
        target = _criteria_target(crit)
        return abs(_num(value) - _num(target)) < 1e-9
    m = re.match(r"^(<=|>=|<>|<|>|=)(.*)$", crit)
    if m:
        op, rest = m.group(1), m.group(2)
        target = _criteria_target(rest)
        if isinstance(target, str) and op == "=":
            return str(value) == target
        av, tv = _num(value), _num(target)
        if op == "<":
            return av < tv
        if op == ">":
            return av > tv
        if op == "<=":
            return av <= tv
        if op == ">=":
            return av >= tv
        if op == "<>":
            return av != tv
        return av == tv
    if crit.startswith("="):
        return str(value) == crit[1:]
    if "*" in crit or "?" in crit:
        pattern = "^" + re.escape(crit).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        return bool(re.match(pattern, str(value), re.I))
    # Текстовый критерий («Дома», «В») — только строковое равенство.
    # Иначе _num("Дома")==0 матчит все пустые ячейки (store отдаёт 0).
    try:
        float(str(crit).replace(",", ".").rstrip("%"))
        numeric_crit = True
    except ValueError:
        numeric_crit = False
    if not numeric_crit:
        if value in (None, ""):
            return False
        return str(value).strip() == crit
    if value in (None, ""):
        return False
    return str(value) == crit or abs(_num(value) - _num(crit)) < 1e-12


def ROUND(v: Value, digits: int = 0) -> float:
    return round(_num(v), int(digits))


def ABS(v: Value) -> float:
    return abs(_num(v))


def SUM(*args: Value) -> float:
    return sum(_nums(args))


def AVERAGE(*args: Value) -> float:
    nums = _nums(args)
    return sum(nums) / len(nums) if nums else 0.0


def MAX(*args: Value) -> float:
    nums = _nums(args)
    return max(nums) if nums else 0.0


def MIN(*args: Value) -> float:
    nums = _nums(args)
    return min(nums) if nums else 0.0


def COUNT(*args: Value) -> int:
    return len([x for x in _flatten(args) if x not in (None, "")])


def COUNTIF(rng: Sequence, criteria: Value) -> int:
    return sum(1 for x in _flatten(rng) if match_criteria(x, criteria))


def SUMIFS(sum_range: Sequence, *criteria_args: Value) -> float:
    sums = _flatten(sum_range)
    if len(criteria_args) % 2 != 0:
        return NA_ERROR
    ranges = []
    crits = []
    for i in range(0, len(criteria_args), 2):
        ranges.append(_flatten(criteria_args[i]))
        crits.append(criteria_args[i + 1])
    total = 0.0
    n = len(sums)
    for i in range(n):
        ok = True
        for rng, crit in zip(ranges, crits):
            val = rng[i] if i < len(rng) else None
            if not match_criteria(val, crit):
                ok = False
                break
        if ok:
            total += _num(sums[i])
    return total


def MATCH(lookup: Value, lookup_array: Sequence, match_type: int = 0) -> int:
    arr = _flatten(list(lookup_array))
    try:
        mt = int(match_type) if not isinstance(match_type, bool) else (0 if match_type is False else 1)
    except (TypeError, ValueError):
        mt = 0
    if match_type is False:
        mt = 0
    if match_type is True:
        mt = 1
    if mt == 0:
        for i, v in enumerate(arr):
            if v == lookup:
                return i + 1
            if isinstance(lookup, str) or isinstance(v, str):
                if str(v) == str(lookup):
                    return i + 1
                continue
            if isinstance(v, (int, float)) and isinstance(lookup, (int, float)):
                if float(v) == float(lookup):
                    return i + 1
        return NA_ERROR
    if mt == 1:
        best = 0
        lv = _num(lookup)
        for i, v in enumerate(arr):
            if v in (None, ""):
                continue
            if _num(v) <= lv:
                best = i + 1
            else:
                break
        return best if best else NA_ERROR
    best = 0
    lv = _num(lookup)
    for i, v in enumerate(arr):
        if v in (None, ""):
            continue
        if _num(v) >= lv:
            best = i + 1
    return best if best else NA_ERROR


def INDEX(array: Sequence, row_num: int, col_num: Optional[int] = None) -> Value:
    rows = list(array)
    if not rows:
        return NA_ERROR
    if isinstance(rows[0], (list, tuple)):
        r = int(row_num) - 1
        if r < 0 or r >= len(rows):
            return NA_ERROR
        row = list(rows[r])
        if col_num is None:
            return row[0] if row else NA_ERROR
        c = int(col_num) - 1
        return row[c] if 0 <= c < len(row) else NA_ERROR
    idx = int(row_num) - 1
    return rows[idx] if 0 <= idx < len(rows) else NA_ERROR


def VLOOKUP(lookup: Value, table_array: Sequence, col_index: int, range_lookup: bool = True) -> Value:
    rows = [list(r) for r in table_array]
    if not rows:
        return NA_ERROR
    col_i = int(col_index) - 1
    # Excel: 4-й аргумент FALSE/0 — точное совпадение (не приближённое).
    exact = range_lookup is False or range_lookup == 0
    if not exact:
        best = None
        lv = _num(lookup)
        for row in rows:
            if not row:
                continue
            if _num(row[0]) <= lv:
                best = row
            else:
                break
        if best is None:
            return NA_ERROR
        return best[col_i] if col_i < len(best) else NA_ERROR
    for row in rows:
        if not row:
            continue
        cell = row[0]
        if cell == lookup:
            return row[col_i] if col_i < len(row) else NA_ERROR
        # Строки: только текстовое равенство. НЕ _num("Орикс")==_num("Игр")==0.
        if isinstance(lookup, str) or isinstance(cell, str):
            if str(cell).strip() == str(lookup).strip():
                return row[col_i] if col_i < len(row) else NA_ERROR
            continue
        if isinstance(cell, (int, float)) and isinstance(lookup, (int, float)):
            if float(cell) == float(lookup):
                return row[col_i] if col_i < len(row) else NA_ERROR
    return NA_ERROR


def HLOOKUP(lookup: Value, table_array: Sequence, row_index: int, range_lookup: bool = True) -> Value:
    rows = [list(r) for r in table_array]
    if not rows:
        return NA_ERROR
    header = rows[0]
    ri = int(row_index) - 1
    exact = range_lookup is False or range_lookup == 0
    if not exact:
        best_col = -1
        lv = _num(lookup)
        for i, h in enumerate(header):
            if _num(h) <= lv:
                best_col = i
            else:
                break
        if best_col < 0:
            return NA_ERROR
        return rows[ri][best_col] if ri < len(rows) else NA_ERROR
    for i, h in enumerate(header):
        if h == lookup:
            return rows[ri][i] if ri < len(rows) and i < len(rows[ri]) else NA_ERROR
        if isinstance(lookup, str) or isinstance(h, str):
            if str(h).strip() == str(lookup).strip():
                return rows[ri][i] if ri < len(rows) and i < len(rows[ri]) else NA_ERROR
            continue
        if isinstance(h, (int, float)) and isinstance(lookup, (int, float)):
            if float(h) == float(lookup):
                return rows[ri][i] if ri < len(rows) and i < len(rows[ri]) else NA_ERROR
    return NA_ERROR


def _fact(n: int) -> float:
    return float(math.factorial(n))


def POISSON_DIST(x: Value, mean: Value, cumulative: bool = False) -> float:
    return POISSON(x, mean, cumulative)


def TREND(known_y: Sequence, known_x: Sequence = None, new_x: Value = None, const: bool = True) -> Value:
    ys = _nums(known_y)
    if not ys:
        return NA_ERROR
    if known_x is None:
        xs = list(range(1, len(ys) + 1))
    else:
        xs = _nums(known_x)
    n = min(len(xs), len(ys))
    xs = xs[:n]
    ys = ys[:n]
    meanx = sum(xs) / n
    meany = sum(ys) / n
    varx = sum((x - meanx) ** 2 for x in xs)
    if const:
        slope = 0.0 if varx == 0 else sum((xs[i] - meanx) * (ys[i] - meany) for i in range(n)) / varx
        intercept = meany - slope * meanx
    else:
        denom = sum(x * x for x in xs)
        slope = 0.0 if denom == 0 else sum(xs[i] * ys[i] for i in range(n)) / denom
        intercept = 0.0

    if new_x is None:
        new_vals = xs
    elif isinstance(new_x, (list, tuple)):
        new_vals = _nums(new_x)
    else:
        return intercept + slope * _num(new_x)
    preds = [intercept + slope * x for x in new_vals]
    return preds[0] if len(preds) == 1 else preds


def LOOKUP(lookup: Value, lookup_vector: Sequence, result_vector: Sequence = None) -> Value:
    keys = _flatten(lookup_vector)
    vals = _flatten(result_vector) if result_vector is not None else keys
    best = -1
    numeric = True
    try:
        lv = _num(lookup)
        if isinstance(lookup, str) and not re.match(r"^-?\d", lookup.strip().replace(",", ".")):
            numeric = False
    except Exception:
        lv = 0.0
        numeric = False
    if numeric and not isinstance(lookup, str):
        numeric = True
    elif isinstance(lookup, str):
        try:
            float(str(lookup).replace(",", ".").replace("%", ""))
        except ValueError:
            numeric = False
    if numeric:
        for i, k in enumerate(keys):
            if k in (None, ""):
                continue
            if _num(k) <= lv:
                best = i
            else:
                break
    else:
        ls = str(lookup)
        for i, k in enumerate(keys):
            if str(k) <= ls:
                best = i
            else:
                break
    if best < 0 or best >= len(vals):
        return NA_ERROR
    return vals[best]


def POISSON(x: Value, mean: Value, cumulative: bool = False) -> float:
    k = int(_num(x))
    lam = _num(mean)
    if lam < 0:
        return NA_ERROR
    if not cumulative:
        if k < 0:
            return 0.0
        return math.exp(-lam) * (lam ** k) / _fact(k)
    total = 0.0
    for i in range(k + 1):
        total += math.exp(-lam) * (lam ** i) / _fact(i)
    return total


def SMALL(array: Sequence, k: int) -> float:
    nums = sorted(_nums(array))
    idx = int(k) - 1
    return nums[idx] if 0 <= idx < len(nums) else NA_ERROR


def MEDIAN(*args: Value) -> float:
    nums = sorted(_nums(args))
    if not nums:
        return 0.0
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2.0


def MOD(number: Value, divisor: Value) -> float:
    d = _num(divisor)
    if d == 0:
        return DIV0_ERROR
    return _num(number) % d


def TRUNC(number: Value, digits: int = 0) -> float:
    return ROUNDDOWN(number, digits)


def VALUE(text: Value) -> float:
    return _num(text)


def CEILING(number: Value, significance: Value = 1) -> float:
    n = _num(number)
    s = _num(significance)
    if s == 0:
        return 0.0
    import math as _m

    return _m.ceil(n / s) * s


def FLOOR(number: Value, significance: Value = 1) -> float:
    n = _num(number)
    s = _num(significance)
    if s == 0:
        return 0.0
    import math as _m

    return _m.floor(n / s) * s


def SUMPRODUCT(*args: Value) -> float:
    if not args:
        return 0.0
    arrays = [_flatten(a) for a in args]
    n = min(len(a) for a in arrays)
    total = 0.0
    for i in range(n):
        prod = 1.0
        for arr in arrays:
            prod *= _num(arr[i])
        total += prod
    return total


def COUNTIFS(*args: Value) -> int:
    if len(args) < 2 or len(args) % 2:
        return NA_ERROR
    ranges = [_flatten(args[i]) for i in range(0, len(args), 2)]
    crits = [args[i] for i in range(1, len(args), 2)]
    n = min(len(r) for r in ranges)
    count = 0
    for i in range(n):
        if all(match_criteria(ranges[ri][i], crits[ri]) for ri in range(len(ranges))):
            count += 1
    return count


def AVEDEV(*args: Value) -> float:
    nums = _nums(args)
    if not nums:
        return 0.0
    mean = sum(nums) / len(nums)
    return sum(abs(x - mean) for x in nums) / len(nums)


def MAXA(*args: Value) -> float:
    return MAX(*args)


def NORM_INV(probability: Value, mean: Value = 0, standard_dev: Value = 1) -> float:
    """Approximate NORM.INV via Beasley-Springer/Moro-ish rational (good enough)."""
    p = _num(probability)
    mu = _num(mean)
    sigma = _num(standard_dev)
    if sigma <= 0 or p <= 0 or p >= 1:
        return NA_ERROR
    # Acklam approximation
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577459334152e02,
        -3.066479806614736e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223726362411991e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    elif p <= phigh:
        q = p - 0.5
        r = q * q
        x = (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    return mu + sigma * x


def RAND() -> float:
    import random

    return random.random()


def LARGE(array: Sequence, k: int) -> float:
    nums = sorted(_nums(array), reverse=True)
    idx = int(k) - 1
    return nums[idx] if 0 <= idx < len(nums) else NA_ERROR


def _text_arg(v: Value) -> str:
    """Аргумент как текст (Excel: числа → General-строка, 0 → '0')."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def SUBSTITUTE(text: Value, old: str, new: str, instance: Optional[int] = None) -> str:
    s = _text_arg(text)
    old_s = _text_arg(old)
    new_s = _text_arg(new)
    if not old_s:
        return s
    parts = s.split(old_s)
    if instance is None:
        return s.replace(old_s, new_s)
    try:
        k = int(_num(instance))
    except Exception:
        k = 0
    if k <= 0 or len(parts) <= k:
        return s
    return old_s.join(parts[:k]) + new_s + old_s.join(parts[k:])


def CONCATENATE(*args: Value) -> str:
    return "".join(str(a if a is not None else "") for a in args)


def TEXT(value: Value, fmt: str) -> str:
    v = _num(value)
    if "0" in fmt and "%" in fmt:
        return f"{v * 100:.0f}%"
    if fmt.lower() in ("dd.mm.yy чч:мм", "dd.mm.yy hh:mm"):
        return str(value)
    return str(value)


def TRIM(v: Value) -> str:
    return str(v or "").strip()


def SEARCH(find_text: str, within_text: Value, start: int = 1) -> int:
    s = str(within_text or "")
    ft = str(find_text)
    idx = s.find(ft, int(start) - 1)
    return idx + 1 if idx >= 0 else NA_ERROR


def ISNUMBER_SEARCH(find_text: str, within_text: Value) -> bool:
    try:
        r = SEARCH(find_text, within_text)
        return r != NA_ERROR
    except Exception:
        return False


def SUBSTITUTE_CHAIN(text: Value, *pairs: str) -> str:
    s = str(text or "")
    i = 0
    while i + 1 < len(pairs):
        s = s.replace(pairs[i], pairs[i + 1])
        i += 2
    return s


FUNCTIONS = {
    "IF": IF,
    "IFERROR": IFERROR,
    "AND": AND,
    "OR": OR,
    "NOT": NOT,
    "ISNUMBER": ISNUMBER,
    "ISERROR": ISERROR,
    "ISEVEN": ISEVEN,
    "ROUND": ROUND,
    "ROUNDDOWN": ROUNDDOWN,
    "ROUNDUP": ROUNDUP,
    "ABS": ABS,
    "SUM": SUM,
    "SUMIFS": SUMIFS,
    "AVERAGE": AVERAGE,
    "MAX": MAX,
    "MIN": MIN,
    "COUNT": COUNT,
    "COUNTIF": COUNTIF,
    "MATCH": MATCH,
    "INDEX": INDEX,
    "VLOOKUP": VLOOKUP,
    "HLOOKUP": HLOOKUP,
    "LOOKUP": LOOKUP,
    "POISSON": POISSON,
    "POISSON.DIST": POISSON_DIST,
    "_XLFN.POISSON.DIST": POISSON_DIST,
    "TREND": TREND,
    "LARGE": LARGE,
    "SMALL": SMALL,
    "MEDIAN": MEDIAN,
    "MOD": MOD,
    "TRUNC": TRUNC,
    "VALUE": VALUE,
    "CEILING": CEILING,
    "FLOOR": FLOOR,
    "SUMPRODUCT": SUMPRODUCT,
    "COUNTIFS": COUNTIFS,
    "AVEDEV": AVEDEV,
    "MAXA": MAXA,
    "NORM.INV": NORM_INV,
    "_XLFN.NORM.INV": NORM_INV,
    "RAND": RAND,
    "SUBSTITUTE": SUBSTITUTE,
    "CONCATENATE": CONCATENATE,
    "TEXT": TEXT,
    "TRIM": TRIM,
    "SEARCH": SEARCH,
}
