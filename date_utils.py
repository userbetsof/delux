"""Нормализация дат матчей к виду YYYY.MM.DD HH:MM (пример: 2026.09.04 12:00)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Union

MATCH_DATE_FMT = "%Y.%m.%d %H:%M"

_FORMATS = (
    "%Y.%m.%d %H:%M",
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%y %H:%M",
    "%d.%m.%y %H:%M:%S",
    "%Y.%m.%d",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d.%m.%y",
)

_DMY_SHORT = re.compile(
    r"^(\d{1,2})\.(\d{1,2})\.(\d{2})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?)?$"
)
_YMD_DOTS = re.compile(
    r"^(\d{4})\.(\d{1,2})\.(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?)?$"
)


def _expand_year(yy: int) -> int:
    """Двухзначный год → полный. 00–79 → 2000–2079, 80–99 → 1980–1999."""
    return 2000 + yy if yy < 80 else 1900 + yy


def _from_parts(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
) -> Optional[datetime]:
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def parse_match_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0)

    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return datetime(
                value.year, value.month, value.day,
                getattr(value, "hour", 0),
                getattr(value, "minute", 0),
            )
        except Exception:
            pass

    text = str(value).strip()
    if not text:
        return None

    m = _DMY_SHORT.match(text)
    if m:
        day, month, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4) or 0)
        minute = int(m.group(5) or 0)
        return _from_parts(_expand_year(yy), month, day, hour, minute)

    m = _YMD_DOTS.match(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4) or 0)
        minute = int(m.group(5) or 0)
        return _from_parts(year, month, day, hour, minute)

    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(second=0, microsecond=0)
        except ValueError:
            continue
    return None


def normalize_match_date(
    value: Union[str, datetime, None],
    *,
    force_year: Optional[int] = None,
) -> str:
    """Любой вход → 'YYYY.MM.DD HH:MM' (пример: 2015.08.08 17:00) или ''.

    Год НЕ подменяется по умолчанию: исторические матчи (2014, 2015, …)
    должны сохранять свой год. force_year передаётся явно только там, где
    источник даёт дату без года (например лента дня текущего сезона).
    """
    dt = parse_match_datetime(value)
    if dt is None:
        return ""
    if force_year is not None and dt.year != force_year:
        try:
            dt = dt.replace(year=int(force_year))
        except ValueError:
            # 29.02 в невисокосном году
            dt = dt.replace(year=int(force_year), day=28)
    return dt.strftime(MATCH_DATE_FMT)


def format_ts_match_date(ts_value: str, timezone: int, time_offset: int = 0) -> str:
    """Unix timestamp → нормализованная дата с учётом TZ."""
    try:
        seconds = int(float(ts_value))
    except (TypeError, ValueError):
        return ""
    dt = datetime(1970, 1, 1) + timedelta(seconds=seconds)
    dt += timedelta(hours=int(timezone) + int(time_offset))
    return dt.strftime(MATCH_DATE_FMT)
