"""Допуск совпадения стратегий / 10 подстратегий (без Excel)."""

from __future__ import annotations

from typing import Any, Dict, List

# Вероятности подстратегий: |Δ| ≤ 1 п.п. (0.01 в долях или 1.0 если значения в %)
STRATEGY_TOL = 0.01


def _norm_pred(val: Any) -> str:
    s = str(val or "").strip()
    if s in ("-", "—", "None"):
        return ""
    return s


def _as_fraction(v: Any) -> float:
    """H/D/A могут быть 0.42 или 42 (%)."""
    x = float(v or 0)
    if x > 1.5:
        return x / 100.0
    return x


def probs_close(a: Any, b: Any, tol: float = STRATEGY_TOL) -> bool:
    try:
        return abs(_as_fraction(a) - _as_fraction(b)) <= tol
    except (TypeError, ValueError):
        return _norm_pred(a) == _norm_pred(b)


def compare_calc_results(
    left: Dict[str, Any],
    right: Dict[str, Any],
    *,
    strategy_tol: float = STRATEGY_TOL,
    left_name: str = "a",
    right_name: str = "b",
) -> List[str]:
    """NTB/Betalone/Sniper — точное совпадение; 10 подстратегий — отклонение ≤ 1%."""
    diffs: List[str] = []
    for key in ("prediction_ntb", "prediction_betalone", "prediction_sniper"):
        lv = _norm_pred(left.get(key))
        rv = _norm_pred(right.get(key))
        if lv != rv:
            diffs.append(f"{key}: {left_name}={left.get(key)!r} {right_name}={right.get(key)!r}")

    lo = left.get("outcome_probabilities") or []
    ro = right.get("outcome_probabilities") or []
    if len(lo) < 10 or len(ro) < 10:
        diffs.append(f"substrategies_count: {left_name}={len(lo)} {right_name}={len(ro)} (need 10)")
    for i in range(min(10, len(lo), len(ro))):
        e, p = lo[i], ro[i]
        for fld in ("home_prob", "draw_prob", "away_prob"):
            if not probs_close(e.get(fld), p.get(fld), strategy_tol):
                diffs.append(
                    f"substrategy[{i}].{fld}: {left_name}={e.get(fld)} {right_name}={p.get(fld)} "
                    f"(tol={strategy_tol})"
                )
    return diffs
