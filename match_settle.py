"""Статусы Flashscore и признак «матч завершён» для расчёта стратегий."""

from __future__ import annotations

import re

STATUSES = {
    "1": "Не начался",
    "45": "Будет доигран позже",
    "42": "Ждем...",
    "2": "Live",
    "14": "1-й период",
    "15": "2-й период",
    "16": "3-й период",
    "6": "Овертайм",
    "7": "Буллиты",
    "46": "Перерыв",
    "3": "Завершен",
    "10": "После овертайма",
    "11": "После буллитов",
    "9": "Неявка",
    "43": "Задержка",
    "36": "Прерван",
    "4": "Перенесен",
    "5": "Отменен",
    "37": "Прерван",
    "54": "Тех. поражение",
    "26": "1-й иннинг",
    "27": "2-й иннинг",
    "28": "3-й иннинг",
    "29": "4-й иннинг",
    "30": "5-й иннинг",
    "31": "6-й иннинг",
    "32": "7-й иннинг",
    "33": "8-й иннинг",
    "34": "9-й иннинг",
    "35": "Экстра-иннинг",
}

_FINISHED_MARKERS = (
    "заверш",
    "законч",
    "finished",
    "ended",
    "после овертайм",
    "после буллит",
    "after extra",
    "after penalt",
    "тех. пораж",
    "неявк",
)

_VOID_MARKERS = (
    "перенес",
    "отмен",
    "прерван",
    "задержк",
    "будет доигран",
)

_NOT_STARTED_MARKERS = (
    "не начал",
    "ждем",
    "неизвестный (1)",
    "неизвестный статус (1)",
)

_UNKNOWN_CODE_RE = re.compile(r"неизвестный(?: статус)?\s*\((\d+)\)", re.I)


def status_label(code: str | None) -> str:
    raw = str(code or "").strip()
    if raw in STATUSES:
        return STATUSES[raw]
    try:
        key = str(int(float(raw.replace(",", "."))))
    except (TypeError, ValueError):
        key = ""
    if key in STATUSES:
        return STATUSES[key]
    return f"Неизвестный ({raw})" if raw else ""


def canonical_status(status: str | None) -> str:
    raw = str(status or "").strip()
    if not raw:
        return ""
    mapped = status_label(raw)
    if mapped and not mapped.lower().startswith("неизвестный"):
        return mapped
    match = _UNKNOWN_CODE_RE.search(raw)
    if match:
        return STATUSES.get(match.group(1), raw)
    return raw


def is_finished_status(status: str | None, score_home=None, score_away=None) -> bool:
    """True только для реально сыгранных матчей (не live / не 0:0 до стартового свистка)."""
    if score_home is None or score_away is None:
        return False
    try:
        total = int(score_home) + int(score_away)
    except (TypeError, ValueError):
        return False
    s = canonical_status(status).lower()
    if any(m in s for m in _VOID_MARKERS):
        return False
    if any(m in s for m in _FINISHED_MARKERS):
        return True
    if not s or any(m in s for m in _NOT_STARTED_MARKERS):
        # Счёт уже есть, а статус так и остался «Не начался» после ночной ленты.
        return total > 0
    return False


def settle_prediction_row(
    prediction: str,
    result_1x2: str,
    total_home: int,
    total_away: int,
    odds: float,
    notes: str | None = None,
    stake: float = 1.0,
) -> tuple[str, float]:
    """Один или два прогноза (WhoScored: «1:2 / Ф2(-0.5)»)."""
    import json

    from matches_check import calc_forecast_result

    pred = (prediction or "").strip()
    if not pred:
        return "Нет прогноза", 0.0
    if "/" not in pred:
        return calc_forecast_result(pred, result_1x2, total_home, total_away, odds or 1.0)

    obj: dict = {}
    if notes:
        try:
            parsed = json.loads(notes)
            if isinstance(parsed, dict):
                obj = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            obj = {}

    total = 0.0
    labels: list[str] = []
    parts = [p.strip() for p in pred.split("/") if p.strip()]
    keys = ("cs", "ah")
    for i, part in enumerate(parts):
        coeff = 0.0
        block = obj.get(keys[i]) if i < len(keys) else None
        if isinstance(block, dict) and block.get("odds"):
            try:
                coeff = float(block["odds"])
            except (TypeError, ValueError):
                coeff = 0.0
        if coeff <= 1 and i == 0:
            coeff = float(odds or 0) or 1.0
        if coeff <= 1:
            coeff = 1.0
        status, profit = calc_forecast_result(part, result_1x2, total_home, total_away, coeff)
        labels.append(status)
        total += float(profit) * (stake if stake else 1.0)
    return " / ".join(labels), total
