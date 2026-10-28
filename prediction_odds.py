"""Проставление коэффициента в прогнозы стратегий (strategy_predictions.odds).

Прогноз вида 'ТБ 1,5' / 'П1' / '1X' / 'Ф1(0)' сопоставляется с каноническим
рынком из таблицы odds ('OVER 1.5', '1X2_1', 'DC_1X', 'HANDICAP HOME 0.0') и
в strategy_predictions.odds попадает лучший (максимальный) кф по провайдерам —
так же, как это делает стратегия 1 пр в src/strategies/onepr.py.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

from odds_normalize import market_key, prediction_market, to_float


def odds_lookup(rows: Iterable[Any]) -> Dict[Tuple[str, Optional[float]], float]:
    """Строки odds → {ключ рынка: лучший кф}."""
    best: Dict[Tuple[str, Optional[float]], float] = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            name = row["market_name"]
            value = row["odds_value"]
        elif isinstance(row, dict):
            name = row.get("market_name")
            value = row.get("odds_value")
        else:
            name = row[0] if len(row) > 1 else None
            value = row[1] if len(row) > 1 else None
        val = to_float(value)
        if val is None or val <= 1:
            continue
        key = market_key(name)
        prev = best.get(key)
        if prev is None or val > prev:
            best[key] = val
    return best


def _synth_zero_handicap(side: str, lookup: Dict[Tuple[str, Optional[float]], float]) -> Optional[float]:
    """Синтезировать кф нулевой форы из соседних линий.

    Способы (по убыванию точности):
    1. Ф(+0.25) и Ф(-0.25) — азиатский сплит вокруг нуля:
          2 / (1/o_plus + 1/o_minus)
    2. Ф(+0.5) и Ф(-0.5) — тоже сплит, но с большим «размытием»:
          аналогичная формула по этим двум линиям.

    side: 'HOME' | 'AWAY'.
    """
    def pair(plus_line: float, minus_line: float) -> Optional[float]:
        plus = lookup.get((f"HANDICAP {side}", plus_line))
        minus = lookup.get((f"HANDICAP {side}", minus_line))
        if not plus or not minus or plus <= 1 or minus <= 1:
            return None
        return round(2.0 / (1.0 / plus + 1.0 / minus), 3)

    # 1) самый точный: ±0.25
    exact = pair(0.25, -0.25)
    if exact:
        return exact
    # 2) грубее: ±0.5 (если буки дали только их)
    return pair(0.5, -0.5)


def _resolve_handicap_zero(
    prediction: Optional[str],
    side: str,
    lookup: Dict[Tuple[str, Optional[float]], float],
    *,
    allow_synth: bool = True,
) -> Optional[float]:
    """Кф форы 0: сначала точная линия, затем синтез из соседних."""
    direct = lookup.get((f"HANDICAP {side}", 0.0))
    if direct:
        return direct
    if not allow_synth:
        return None
    return _synth_zero_handicap(side, lookup)


def resolve_prediction_odds(
    prediction: Optional[str],
    lookup: Dict[Tuple[str, Optional[float]], float],
) -> Optional[float]:
    """Кф для прогноза по словарю рынков (None, если рынка нет).

    Для форы 0 при отсутствии прямой линии — синтез из ±0.25.
    Для составного прогноза ('1X + ТБ 2,5') кф считается перемножением
    коэффициентов каждой части — как в ставке на комбинацию.
    """
    market = prediction_market(prediction)
    if market:
        key = market_key(market)
        direct = lookup.get(key)
        if direct:
            return direct
        # Фора 0: fallback из ±0.25 (см. _synth_zero_handicap).
        name, line = key
        if name.startswith("HANDICAP ") and line == 0.0:
            side = name.split(" ", 1)[1]
            return _synth_zero_handicap(side, lookup)
        return None

    raw = (prediction or "").strip().upper().replace("Х", "X").replace("Ё", "Е")
    if "+" not in raw:
        return None
    parts = [p.strip() for p in raw.split("+") if p.strip()]
    if len(parts) < 2:
        return None
    combined = 1.0
    for part in parts:
        part_market = prediction_market(part)
        if not part_market:
            return None
        pkey = market_key(part_market)
        value = lookup.get(pkey)
        if not value:
            name, line = pkey
            if name.startswith("HANDICAP ") and line == 0.0:
                value = _synth_zero_handicap(name.split(" ", 1)[1], lookup)
        if not value:
            return None
        combined *= value
    return round(combined, 3) if combined > 1 else None


def _missing_odds_where() -> str:
    return "(odds IS NULL OR odds = '' OR odds <= 1)"


def fill_prediction_odds(
    conn: sqlite3.Connection,
    match_id: Optional[str] = None,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> List[Tuple[str, int, str, float]]:
    """Заполняет strategy_predictions.odds по таблице odds.

    match_id=None — пройти по всем матчам. Возвращает список изменений
    (match_id, strategy_id, prediction, odds).
    """
    cursor = conn.cursor()
    if match_id:
        match_ids = [match_id]
    else:
        match_ids = [
            r[0]
            for r in cursor.execute(
                "SELECT DISTINCT match_id FROM strategy_predictions"
            ).fetchall()
        ]

    changes: List[Tuple[str, int, str, float]] = []
    for mid in match_ids:
        rows = cursor.execute(
            "SELECT market_name, odds_value FROM odds WHERE match_id = ?",
            (mid,),
        ).fetchall()
        if not rows:
            continue
        lookup = odds_lookup(rows)
        where = "match_id = ?" if overwrite else f"match_id = ? AND {_missing_odds_where()}"
        preds = cursor.execute(
            f"SELECT id, strategy_id, prediction FROM strategy_predictions WHERE {where}",
            (mid,),
        ).fetchall()
        for prow in preds:
            row_id = prow["id"] if hasattr(prow, "keys") else prow[0]
            sid = prow["strategy_id"] if hasattr(prow, "keys") else prow[1]
            pred = prow["prediction"] if hasattr(prow, "keys") else prow[2]
            value = resolve_prediction_odds(pred, lookup)
            if value is None:
                continue
            changes.append((mid, int(sid), str(pred), float(value)))
            if not dry_run:
                cursor.execute(
                    "UPDATE strategy_predictions SET odds = ? WHERE id = ?",
                    (float(value), row_id),
                )
    if not dry_run and changes:
        conn.commit()
    return changes
