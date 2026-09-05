"""Сравнение 10 стратегий Excel vs Python (допуск 1%)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import build_settings, load_analysis_data
from calc_engine import ExcelCalcEngine
from formula_port.engine import PythonCalcEngine
from match_store import get_queued_match
from odds_service import load_odds
from settings import DeluxSettings

TOL = 0.01


def main() -> int:
    mid = sys.argv[1] if len(sys.argv) > 1 else "G8d2h42n"
    cfg = DeluxSettings.from_env()
    q = get_queued_match(mid)
    assert q, mid
    ms = build_settings(
        sport=q.sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )
    payload_match = q.to_match_info()
    code, odds = load_odds(mid, ms.source)
    if code != 0 or odds is None:
        print(f"[-] odds failed code={code}")
        return 1
    if odds.home_id:
        payload_match.home_participant_id = odds.home_id
    if odds.away_id:
        payload_match.away_participant_id = odds.away_id
    payload = load_analysis_data(payload_match, ms)
    if odds.home_id:
        payload.match.home_participant_id = odds.home_id
    if odds.away_id:
        payload.match.away_participant_id = odds.away_id
    wb = cfg.resolve_calc_workbook()

    with ExcelCalcEngine(wb, fresh=True) as eng:
        ex = eng.run(payload, odds)
    pr = PythonCalcEngine(wb, pure_eval=True).run(payload, odds)

    print(f"match {mid} | {ex.get('home')} - {ex.get('away')}")
    print(
        f"NTB excel={ex.get('prediction_ntb')!r} py={pr.get('prediction_ntb')!r} | "
        f"Betalone excel={ex.get('prediction_betalone')!r} py={pr.get('prediction_betalone')!r} | "
        f"Sniper excel={ex.get('prediction_sniper')!r} py={pr.get('prediction_sniper')!r}"
    )
    ok = 0
    for i in range(10):
        e = (ex.get("outcome_probabilities") or [{}])[i]
        p = (pr.get("outcome_probabilities") or [{}])[i]
        diffs = []
        for fld in ("home_prob", "draw_prob", "away_prob"):
            ev, pv = float(e.get(fld) or 0), float(p.get(fld) or 0)
            if abs(ev - pv) > TOL:
                diffs.append(f"{fld}: {ev:.4f} vs {pv:.4f}")
        status = "OK" if not diffs else "FAIL"
        if not diffs:
            ok += 1
        print(f"  strat[{i}] {status}  excel=({e.get('home_prob'):.4f},{e.get('draw_prob'):.4f},{e.get('away_prob'):.4f})  "
              f"py=({p.get('home_prob'):.4f},{p.get('draw_prob'):.4f},{p.get('away_prob'):.4f})"
              + (f"  {'; '.join(diffs)}" if diffs else ""))
    print(f"[+] strategies OK {ok}/10 (tol={TOL})")
    return 0 if ok == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
