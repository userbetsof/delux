"""Стратегия Moneyway / Dogs (#7): Arbworld max odds = max volume."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DOGS_STRATEGY_ID = 7
_DELUX_DIR = Path(__file__).resolve().parent
_SIBLING_DOGS = _DELUX_DIR.parent / "dogs"
DEFAULT_DOGS_ROOT = (
    _SIBLING_DOGS
    if (_SIBLING_DOGS / "arbworld_mw").is_dir()
    else Path(r"C:\papki\work\bets\dogs")
)

_ARBWORLD_CACHE: Optional[Dict[Tuple[str, str], Any]] = None
_ARBWORLD_CACHE_FAILED = False
_ARBWORLD_FAIL_REASON = ""


def _dogs_root(explicit: Optional[str] = None) -> Path:
    raw = (explicit or os.environ.get("DOGS_ROOT", "")).strip()
    root = Path(raw) if raw else DEFAULT_DOGS_ROOT
    try:
        return root.expanduser().resolve()
    except OSError:
        return root.expanduser().absolute()


def _ensure_dogs_import(root: Optional[str] = None) -> Path:
    """Добавить корень dogs в sys.path и проверить пакет arbworld_mw."""
    dogs_root = _dogs_root(root)
    package_dir = dogs_root / "arbworld_mw"
    if not package_dir.is_dir():
        raise ModuleNotFoundError(
            f"arbworld_mw not found under DOGS_ROOT={dogs_root} "
            f"(expected {package_dir})"
        )

    path = str(dogs_root)
    normalized = {os.path.normcase(os.path.normpath(p)) for p in sys.path if p}
    if os.path.normcase(os.path.normpath(path)) not in normalized:
        sys.path.insert(0, path)
    elif path not in sys.path:
        sys.path.insert(0, path)

    return dogs_root


def _norm_team(name: str) -> str:
    return (name or "").strip().casefold()


def _lookup_arbworld_row(
    home: str,
    away: str,
    index: Dict[Tuple[str, str], Any],
) -> Tuple[Any, str, str]:
    """
    Найти строку Arbworld по Flashscore-именам с учётом маппинга teams.name_arbworld.
    Возвращает (row|None, home_used, away_used).
    """
    home_fs = (home or "").strip()
    away_fs = (away or "").strip()
    candidates: list[Tuple[str, str]] = [(home_fs, away_fs)]

    mapping = _arbworld_alias_map()
    home_aw = mapping.get(_norm_team(home_fs)) or home_fs
    away_aw = mapping.get(_norm_team(away_fs)) or away_fs
    if (home_aw, away_aw) != (home_fs, away_fs):
        candidates.append((home_aw, away_aw))

    for h, a in candidates:
        row = index.get((_norm_team(h), _norm_team(a)))
        if row is not None:
            return row, h, a
    return None, home_fs, away_fs


_ARBWORLD_ALIAS_CACHE: Optional[Dict[str, str]] = None


def _arbworld_alias_map() -> Dict[str, str]:
    global _ARBWORLD_ALIAS_CACHE
    if _ARBWORLD_ALIAS_CACHE is not None:
        return _ARBWORLD_ALIAS_CACHE
    try:
        from db import load_team_name_map

        _ARBWORLD_ALIAS_CACHE = load_team_name_map("arbworld")
    except Exception:
        _ARBWORLD_ALIAS_CACHE = {}
    return _ARBWORLD_ALIAS_CACHE


def clear_arbworld_alias_cache() -> None:
    global _ARBWORLD_ALIAS_CACHE
    _ARBWORLD_ALIAS_CACHE = None


def fetch_arbworld_index(*, dogs_root: Optional[str] = None) -> Dict[Tuple[str, str], Any]:
    _ensure_dogs_import(dogs_root)
    from arbworld_mw.client import ArbworldClient
    from arbworld_mw.models import RunnerRow

    client = ArbworldClient()
    payload = client.fetch_runners_json()
    index: Dict[Tuple[str, str], RunnerRow] = {}
    for raw in payload.get("data") or []:
        try:
            row = RunnerRow.from_api_dict(raw)
        except (KeyError, TypeError, ValueError):
            continue
        key = (_norm_team(row.home), _norm_team(row.away))
        index[key] = row
    return index


def get_arbworld_index(
    *,
    dogs_root: Optional[str] = None,
    force: bool = False,
    allow_fail: bool = True,
) -> Optional[Dict[Tuple[str, str], Any]]:
    """Один fetch Arbworld на процесс (для batch-анализа)."""
    global _ARBWORLD_CACHE, _ARBWORLD_CACHE_FAILED, _ARBWORLD_FAIL_REASON
    if force:
        _ARBWORLD_CACHE = None
        _ARBWORLD_CACHE_FAILED = False
        _ARBWORLD_FAIL_REASON = ""
    if _ARBWORLD_CACHE is not None:
        return _ARBWORLD_CACHE
    if _ARBWORLD_CACHE_FAILED and not force:
        return None
    try:
        _ARBWORLD_CACHE = fetch_arbworld_index(dogs_root=dogs_root)
        _ARBWORLD_FAIL_REASON = ""
        return _ARBWORLD_CACHE
    except Exception as exc:
        _ARBWORLD_CACHE_FAILED = True
        _ARBWORLD_FAIL_REASON = f"{type(exc).__name__}: {exc}"
        if allow_fail:
            return None
        raise


def last_arbworld_error() -> str:
    return _ARBWORLD_FAIL_REASON


def build_moneyway_snapshot(
    home: str,
    away: str,
    *,
    sport: int = 1,
    arbworld_index: Optional[Dict[Tuple[str, str], Any]] = None,
    dogs_root: Optional[str] = None,
    volume_floor: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Снимок Moneyway для анализируемого матча.
    Всегда возвращает dict для футбола (found=0 если матча нет в Arbworld).
    """
    if int(sport or 1) != 1:
        return None

    if arbworld_index is None and _ARBWORLD_CACHE_FAILED and _ARBWORLD_CACHE is None:
        return {
            "home_name": home,
            "away_name": away,
            "found": False,
            "has_signal": False,
            "signal_side": None,
            "signal_odds": None,
            "raw_json": json.dumps(
                {"error": last_arbworld_error() or "arbworld unavailable"},
                ensure_ascii=False,
            ),
        }

    _ensure_dogs_import(dogs_root)
    from arbworld_mw.config import SIGNAL_VOLUME_MIN
    from arbworld_mw.profit import coef_for_side
    from arbworld_mw.signals import evaluate_moneyway_favorite_volume_signal

    if arbworld_index is not None:
        index = arbworld_index
    else:
        index = get_arbworld_index(dogs_root=dogs_root)
        if index is None:
            return {
                "home_name": home,
                "away_name": away,
                "found": False,
                "has_signal": False,
                "signal_side": None,
                "signal_odds": None,
                "raw_json": json.dumps(
                    {"error": last_arbworld_error() or "arbworld unavailable"},
                    ensure_ascii=False,
                ),
            }

    floor = float(volume_floor if volume_floor is not None else SIGNAL_VOLUME_MIN)
    row, home_used, away_used = _lookup_arbworld_row(home, away, index)
    if row is None:
        return {
            "home_name": home,
            "away_name": away,
            "found": False,
            "has_signal": False,
            "signal_side": None,
            "signal_odds": None,
            "volume_floor": floor,
            "raw_json": json.dumps(
                {
                    "found": False,
                    "lookup_home": home_used,
                    "lookup_away": away_used,
                },
                ensure_ascii=False,
            ),
        }

    is_sig, side = evaluate_moneyway_favorite_volume_signal(row, volume_floor=floor)
    odds = None
    if is_sig and side is not None:
        odds = coef_for_side(side, coef_1=row.coef_1, coef_x=row.coef_x, coef_2=row.coef_2)

    payload = {
        "source": "arbworld_mw",
        "found": True,
        "market_id": row.market_id,
        "coef_1": row.coef_1,
        "coef_x": row.coef_x,
        "coef_2": row.coef_2,
        "volume_1": row.volume_1,
        "volume_x": row.volume_x,
        "volume_2": row.volume_2,
        "volume_floor": floor,
        "league": row.league,
        "event_start": row.event_start.isoformat(sep=" "),
        "has_signal": bool(is_sig and side is not None),
        "signal_side": side,
        "signal_odds": odds,
        "flashscore_home": home,
        "flashscore_away": away,
        "arbworld_home": row.home,
        "arbworld_away": row.away,
        "lookup_home": home_used,
        "lookup_away": away_used,
    }
    return {
        "home_name": home,
        "away_name": away,
        "found": True,
        "market_id": row.market_id,
        "coef_1": row.coef_1,
        "coef_x": row.coef_x,
        "coef_2": row.coef_2,
        "volume_1": row.volume_1,
        "volume_x": row.volume_x,
        "volume_2": row.volume_2,
        "volume_floor": floor,
        "league": row.league,
        "event_start": row.event_start.isoformat(sep=" "),
        "has_signal": bool(is_sig and side is not None),
        "signal_side": side,
        "signal_odds": odds,
        "raw_json": json.dumps(payload, ensure_ascii=False),
        "notes": json.dumps(payload, ensure_ascii=False),
    }


def compute_dogs_prediction(
    home: str,
    away: str,
    *,
    sport: int = 1,
    arbworld_index: Optional[Dict[Tuple[str, str], Any]] = None,
    dogs_root: Optional[str] = None,
    volume_floor: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    snap = build_moneyway_snapshot(
        home,
        away,
        sport=sport,
        arbworld_index=arbworld_index,
        dogs_root=dogs_root,
        volume_floor=volume_floor,
    )
    if not snap or not snap.get("has_signal") or not snap.get("signal_side"):
        return None
    return {
        "prediction": snap["signal_side"],
        "odds": snap.get("signal_odds"),
        "notes": snap.get("notes") or snap.get("raw_json"),
        "snapshot": snap,
    }
