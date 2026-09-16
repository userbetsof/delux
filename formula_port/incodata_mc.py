"""IncoData: гистограммы голов без 50k RAND-формул (эквивалент NORM.INV + ROUND)."""

from __future__ import annotations

import random
from typing import List, Sequence

from formula_port.cell_store import CellStore
from sheets_config import SHEET_AWAY_AWAY, SHEET_HOME_HOME

SHEET_INCO = "IncoData"
GOAL_MAX = 12
GOAL_BINS = GOAL_MAX + 1  # 0..12


def _avedev(vals: Sequence[float]) -> float:
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return sum(abs(x - m) for x in vals) / len(vals)


def _f(store: CellStore, sheet: str, addr: str) -> float:
    v = store.get(sheet, addr)
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _goal_series(store: CellStore, sheet: str, col: str, start: int = 2, n: int = 5) -> List[float]:
    out: List[float] = []
    for i in range(n):
        out.append(_f(store, sheet, f"{col}{start + i}"))
    return out


def _histogram(
    n: int,
    mean_a: float,
    sig_a: float,
    mean_b: float,
    sig_b: float,
    rng: random.Random,
) -> List[int]:
    """Счётчики ROUND((N(μa,σa)+N(μb,σb))/2) для голов 0..GOAL_MAX (хвост в 12)."""
    sig_a = max(sig_a, 1e-9)
    sig_b = max(sig_b, 1e-9)
    hist = [0] * GOAL_BINS
    for _ in range(n):
        ae = rng.gauss(mean_a, sig_a)
        af = rng.gauss(mean_b, sig_b)
        goals = int(round((ae + af) / 2.0))
        if goals < 0:
            continue
        if goals > GOAL_MAX:
            goals = GOAL_MAX
        hist[goals] += 1
    return hist


def apply_incodata_goal_probs(store: CellStore, *, n: int = 50_000, seed: int = 42) -> None:
    """
    Заполняет IncoData!AT21:AT{20+GOAL_BINS} и AW (и AS/AV) — вероятности 0..12 голов.
    """
    # ДомаДома L/M → I/J; ГостиГости L/M → N/O  (как формулы I4/J4/N4/O4)
    home_scored = _goal_series(store, SHEET_HOME_HOME, "L")  # I4:I8
    home_conceded = _goal_series(store, SHEET_HOME_HOME, "M")  # J4:J8
    away_scored = _goal_series(store, SHEET_AWAY_AWAY, "L")  # N4:N8
    away_conceded = _goal_series(store, SHEET_AWAY_AWAY, "M")  # O4:O8

    i10 = sum(home_scored) / 5.0
    j10 = sum(home_conceded) / 5.0
    n10 = sum(away_scored) / 5.0
    o10 = sum(away_conceded) / 5.0
    i20 = _avedev(home_scored)
    j20 = _avedev(home_conceded)
    n20 = _avedev(away_scored)
    o20 = _avedev(away_conceded)

    # Odd rows (AH): means Z3=I10, AA3=O10, sigs I20, O20
    # Even rows (AI): means Z4=N10, AA4=J10, sigs N20, J20
    rng = random.Random(seed)
    hist_home = _histogram(n, i10, i20, o10, o20, rng)
    hist_away = _histogram(n, n10, n20, j10, j20, rng)

    for k in range(GOAL_BINS):
        row = 21 + k
        store.set_value(SHEET_INCO, f"AS{row}", float(hist_home[k]))
        store.set_value(SHEET_INCO, f"AT{row}", hist_home[k] / float(n))
        store.set_value(SHEET_INCO, f"AV{row}", float(hist_away[k]))
        store.set_value(SHEET_INCO, f"AW{row}", hist_away[k] / float(n))
        # убрать формулы, чтобы eval не затирал нулями
        store._formulas.pop(store.key(SHEET_INCO, f"AS{row}"), None)
        store._formulas.pop(store.key(SHEET_INCO, f"AT{row}"), None)
        store._formulas.pop(store.key(SHEET_INCO, f"AV{row}"), None)
        store._formulas.pop(store.key(SHEET_INCO, f"AW{row}"), None)
