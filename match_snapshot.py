"""Снимок данных матча на момент анализа.

Инфо о матче (судья, стадион, город, вместимость, зрители) — из фида df_sui,
таблица, форма, матчи команд и личные встречи — из AnalysisPayload.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional

from flashscore_feed import FIELD_SEP, FLASHSCORE_SOURCER, ROW_SEP, fetch_feed

# MIT-код Flashscore → поле снимка
INFO_FIELDS = {
    "REF": "referee",
    "RCC": "referee_country",
    "RCO": "referee_country_id",
    "VEN": "venue",
    "TWN": "town",
    "CAP": "capacity",
    "ATT": "attendance",
}

INT_FIELDS = ("capacity", "attendance")


def info_feed_url(match_id: str, *, sport: int = 1, sourcer: str = FLASHSCORE_SOURCER) -> str:
    return f"https://{sourcer}x/feed/df_sui_{int(sport)}_{match_id}"


def _to_int(value: str) -> Optional[int]:
    """«75 024» → 75024."""
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else None


def parse_info_pairs(text: str) -> Dict[str, str]:
    """MIT÷REF¬MIV÷Obrenovic R.¬… → {'REF': 'Obrenovic R.', …} (все ключи как есть)."""
    pairs: Dict[str, str] = {}
    pending = ""
    for chunk in (text or "").replace("~", ROW_SEP).split(ROW_SEP):
        key, sep, value = chunk.partition(FIELD_SEP)
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "MIT":
            pending = value.upper()
        elif key == "MIV":
            if pending and value:
                pairs[pending] = value
            pending = ""
    return pairs


def parse_match_info(text: str) -> Dict[str, Any]:
    """Нормализованные поля снимка из фида df_sui."""
    pairs = parse_info_pairs(text)
    out: Dict[str, Any] = {}
    for code, name in INFO_FIELDS.items():
        value = pairs.get(code)
        if not value:
            continue
        out[name] = _to_int(value) if name in INT_FIELDS else value
    if pairs:
        out["raw_json"] = json.dumps(pairs, ensure_ascii=False)
    return out


def fetch_match_info(
    match_id: str,
    *,
    sport: int = 1,
    sourcer: str = FLASHSCORE_SOURCER,
) -> Dict[str, Any]:
    url = info_feed_url(match_id, sport=sport, sourcer=sourcer)
    return parse_match_info(fetch_feed(url))


def save_match_info(
    match_id: str,
    *,
    sport: int = 1,
    sourcer: str = FLASHSCORE_SOURCER,
    info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Забрать инфо о матче и записать в match_snapshot."""
    if not match_id:
        return {}
    data = info if info is not None else fetch_match_info(match_id, sport=sport, sourcer=sourcer)
    if not data:
        return {}

    from db import upsert_match_snapshot

    upsert_match_snapshot(match_id, data)
    return data


def _rows(items: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
    """Строки (dataclass / dict / простой объект) → список словарей.

    Важно: match_analysis создаёт строки через type("TableRow", (), {...}) —
    это НЕ dataclass, и раньше они молча отбрасывались, из-за чего
    standings_json оставался пустым.
    """
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if is_dataclass(item) and not isinstance(item, type):
            out.append(asdict(item))
        elif isinstance(item, dict):
            out.append(dict(item))
        else:
            # Обычный объект-строка: атрибуты могут лежать как в экземпляре,
            # так и в классе (type("TableRow", (), {...})()).
            data: Dict[str, Any] = {}
            for source in (getattr(item, "__dict__", {}) or {}, vars(type(item))):
                for key, value in source.items():
                    if key.startswith("_"):
                        continue
                    data.setdefault(key, value)
            if data:
                out.append(data)
    return out


def _json_or_none(data: Dict[str, Any]) -> Optional[str]:
    """None, если во всех секциях пусто — тогда upsert не затрёт прежний снимок."""
    if not any(data.values()):
        return None
    return json.dumps(data, ensure_ascii=False)


def build_payload_snapshot(payload: Any) -> Dict[str, Any]:
    """Таблица, форма, матчи команд и личные встречи из данных анализа."""
    standings = {
        "overall": _rows(getattr(payload, "table_overall", None)),
        "home": _rows(getattr(payload, "table_home", None)),
        "away": _rows(getattr(payload, "table_away", None)),
    }
    form = {
        "overall": _rows(getattr(payload, "form_overall", None)),
        "home": _rows(getattr(payload, "form_home", None)),
        "away": _rows(getattr(payload, "form_away", None)),
    }
    h2h = {
        "all": _rows(getattr(payload, "h2h", None)),
        "home": _rows(getattr(payload, "h2h_home", None)),
    }
    team_matches = {
        "home": {
            "all": _rows(getattr(payload, "home_all", None)),
            "home": _rows(getattr(payload, "home_home", None)),
            "away": _rows(getattr(payload, "home_away", None)),
        },
        "away": {
            "all": _rows(getattr(payload, "away_all", None)),
            "home": _rows(getattr(payload, "away_home", None)),
            "away": _rows(getattr(payload, "away_away", None)),
        },
    }
    return {
        "standings_json": _json_or_none(standings),
        "form_json": _json_or_none(form),
        "h2h_json": _json_or_none(h2h),
        "team_matches_json": _json_or_none(
            {"home": team_matches["home"], "away": team_matches["away"]}
            if any(team_matches["home"].values()) or any(team_matches["away"].values())
            else {}
        ),
    }


def save_payload_snapshot(match_id: str, payload: Any) -> Dict[str, Any]:
    """Записать таблицу/форму/матчи/H2H в match_snapshot."""
    if not match_id or payload is None:
        return {}
    data = build_payload_snapshot(payload)
    if not any(data.values()):
        return {}

    from db import upsert_match_snapshot

    upsert_match_snapshot(match_id, data)
    return data


def describe_payload_snapshot(payload: Any) -> str:
    """Короткая строка для лога анализа."""
    bits = []
    table = len(_rows(getattr(payload, "table_overall", None)))
    if table:
        bits.append(f"таблица {table}")
    h2h = len(_rows(getattr(payload, "h2h", None)))
    if h2h:
        bits.append(f"H2H {h2h}")
    home = len(_rows(getattr(payload, "home_all", None)))
    away = len(_rows(getattr(payload, "away_all", None)))
    if home or away:
        bits.append(f"матчи {home}/{away}")
    return ", ".join(bits)


def describe_match_info(info: Dict[str, Any]) -> str:
    """Короткая строка для лога анализа."""
    bits = []
    venue = " / ".join(str(info[k]) for k in ("venue", "town") if info.get(k))
    if venue:
        bits.append(venue)
    if info.get("capacity"):
        bits.append(f"вместимость {info['capacity']}")
    if info.get("attendance"):
        bits.append(f"зрителей {info['attendance']}")
    referee = str(info.get("referee") or "")
    if referee:
        country = str(info.get("referee_country") or "")
        bits.append(f"судья {referee}{f' ({country})' if country else ''}")
    return ", ".join(bits)
