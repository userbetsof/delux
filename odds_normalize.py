"""Канонические имена рынков коэффициентов (1X2_1, OVER 2.5, …)."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def to_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        try:
            return float(str(v).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None


def canonicalize_market(
    market_name: Optional[str],
    *,
    outcome: Optional[str] = None,
    side: Optional[str] = None,
    line_value: Any = None,
) -> Optional[str]:
    """Приводит запись odds к каноническому market_name."""
    raw = (market_name or "").strip()
    if not raw and outcome is None and side is None:
        return None

    upper = raw.upper().replace(",", ".")
    line = to_float(line_value)
    out = (outcome or "").strip().upper()
    sd = (side or "").strip().upper()

    # Already canonical
    if upper in ("1X2_1", "1X2_X", "1X2_2", "BTTS_YES", "BTTS_NO", "DC_1X", "DC_12", "DC_X2"):
        return upper
    if upper.startswith(("OVER ", "UNDER ", "1ST HALF OVER ", "1ST HALF UNDER ", "HANDICAP HOME ", "HANDICAP AWAY ")):
        return upper

    # Collapsed 1X2 / 1x2 + outcome / wide implied
    if upper in ("1X2", "1x2".upper()):
        mapping = {
            "HOME": "1X2_1",
            "1": "1X2_1",
            "H": "1X2_1",
            "DRAW": "1X2_X",
            "X": "1X2_X",
            "D": "1X2_X",
            "AWAY": "1X2_2",
            "2": "1X2_2",
            "A": "1X2_2",
        }
        if out in mapping:
            return mapping[out]
        return None

    if upper == "BTTS":
        if out in ("YES", "Y", "TRUE", "1"):
            return "BTTS_YES"
        if out in ("NO", "N", "FALSE", "0"):
            return "BTTS_NO"
        return None

    if upper == "DC":
        if out in ("1X", "HOME_DRAW"):
            return "DC_1X"
        if out in ("12", "HOME_AWAY"):
            return "DC_12"
        if out in ("X2", "DRAW_AWAY"):
            return "DC_X2"
        return None

    if upper == "OVER" and line is not None:
        return f"OVER {line:g}"
    if upper == "UNDER" and line is not None:
        return f"UNDER {line:g}"

    if "HANDICAP" in upper:
        if sd in ("HOME", "H", "1") or out in ("HOME", "H", "1"):
            side_l = "HOME"
        elif sd in ("AWAY", "A", "2") or out in ("AWAY", "A", "2"):
            side_l = "AWAY"
        else:
            m = re.search(r"HANDICAP\s+(HOME|AWAY)", upper)
            side_l = m.group(1) if m else None
        if side_l is None:
            return None
        if line is None:
            m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", upper)
            line = to_float(m.group(1)) if m else None
        if line is None:
            return None
        return f"HANDICAP {side_l} {line:g}"

    # HALF totals collapsed
    if "1ST HALF" in upper or "FIRST" in upper:
        if "OVER" in upper and line is not None:
            return f"1st Half OVER {line:g}"
        if "UNDER" in upper and line is not None:
            return f"1st Half UNDER {line:g}"

    return raw if raw else None


def split_canonical(market_name: str) -> Dict[str, Any]:
    """Обратно: outcome/side/line из канонического имени."""
    key = (market_name or "").strip().upper()
    info: Dict[str, Any] = {
        "market_name": market_name,
        "outcome": None,
        "side": None,
        "line_value": None,
    }
    if key == "1X2_1":
        info["outcome"] = "Home"
    elif key == "1X2_X":
        info["outcome"] = "Draw"
    elif key == "1X2_2":
        info["outcome"] = "Away"
    elif key == "BTTS_YES":
        info["outcome"] = "YES"
    elif key == "BTTS_NO":
        info["outcome"] = "NO"
    elif key == "DC_1X":
        info["outcome"] = "1X"
    elif key == "DC_12":
        info["outcome"] = "12"
    elif key == "DC_X2":
        info["outcome"] = "X2"
    elif key.startswith("OVER "):
        info["line_value"] = to_float(key.split()[-1])
    elif key.startswith("UNDER "):
        info["line_value"] = to_float(key.split()[-1])
    elif key.startswith("1ST HALF OVER "):
        info["line_value"] = to_float(key.split()[-1])
    elif key.startswith("1ST HALF UNDER "):
        info["line_value"] = to_float(key.split()[-1])
    elif key.startswith("HANDICAP HOME "):
        info["side"] = "HOME"
        info["line_value"] = to_float(key.split()[-1])
    elif key.startswith("HANDICAP AWAY "):
        info["side"] = "AWAY"
        info["line_value"] = to_float(key.split()[-1])
    return info


def expand_wide_1x2_row(row: Dict[str, Any]) -> list[Tuple[str, float]]:
    """Строка со старыми колонками home_win_odds/draw_odds/… → канонические пары."""
    out: list[Tuple[str, float]] = []
    mapping = (
        ("home_win_odds", "1X2_1"),
        ("draw_odds", "1X2_X"),
        ("away_win_odds", "1X2_2"),
        ("odds_1x", "DC_1X"),
        ("odds_12", "DC_12"),
        ("odds_2x", "DC_X2"),
    )
    for col, key in mapping:
        ov = to_float(row.get(col))
        if ov and ov > 1:
            out.append((key, ov))
    return out
