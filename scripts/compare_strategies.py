"""Проверка 10 подстратегий Python-calc (допуск 1%). Excel не требуется."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import build_settings, load_analysis_data
from calc_backend import get_calc_engine
from formula_port.parity import STRATEGY_TOL, compare_calc_results
from match_store import get_queued_match
from odds_service import load_odds
from settings import DeluxSettings


def _print_substrats(results: dict) -> None:
    probs = results.get("outcome_probabilities") or []
    print("  подстратегии (H / D / A):")
    for i, row in enumerate(probs[:10]):
        print(
            f"    [{i}] {float(row.get('home_prob') or 0):.4f}  "
            f"{float(row.get('draw_prob') or 0):.4f}  "
            f"{float(row.get('away_prob') or 0):.4f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Python-calc: стратегии и 10 подстратегий")
    parser.add_argument("match_id", nargs="?", default="")
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Опционально сравнить с Excel COM (если .xlsm есть), допуск 1%",
    )
    parser.add_argument("--tol", type=float, default=STRATEGY_TOL)
    args = parser.parse_args()

    cfg = DeluxSettings.from_env()
    mid = args.match_id or ""
    if not mid:
        from match_store import list_queued_matches

        queued_list = list_queued_matches(leagues_by_sport=cfg.leagues_by_sport, new_only=False, limit=1)
        if not queued_list:
            print("[-] нет матча в очереди, укажите match_id")
            return 1
        q = queued_list[0]
        mid = q.match_id
    else:
        q = get_queued_match(mid)
        if not q:
            print(f"[-] матч {mid} не в очереди")
            return 1

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

    with get_calc_engine(cfg) as eng:
        py = eng.run(payload, odds)

    print(f"match {mid} | {py.get('home')} - {py.get('away')}")
    print(
        f"NTB={py.get('prediction_ntb')!r}  "
        f"Betalone={py.get('prediction_betalone')!r}  "
        f"Sniper={py.get('prediction_sniper')!r}"
    )
    _print_substrats(py)

    if not args.excel:
        print(f"[+] Python-calc без Excel (допуск подстратегий {args.tol})")
        return 0

    try:
        wb = cfg.resolve_calc_workbook()
    except FileNotFoundError as exc:
        print(f"[-] Excel недоступен: {exc}")
        return 1
    from calc_engine import ExcelCalcEngine

    with ExcelCalcEngine(wb, fresh=True) as eng:
        ex = eng.run(payload, odds)
    diffs = compare_calc_results(ex, py, strategy_tol=args.tol, left_name="excel", right_name="python")
    if diffs:
        print("[-] расхождение Excel vs Python:")
        for line in diffs:
            print(f"    {line}")
        return 1
    print(f"[+] Excel vs Python: стратегии и 10 подстратегий совпали (tol={args.tol})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
