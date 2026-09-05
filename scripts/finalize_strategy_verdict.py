"""Honest substrategy metrics: accuracy always; ROI only with real odds."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from scripts.analyze_strategy_profit import load_odds_index, settle_1x2, summarize

OUT = ROOT / "data" / "strategy_profit_report.json"


def main():
    conn = sqlite3.connect("matches.db")
    conn.row_factory = sqlite3.Row
    odds_idx = load_odds_index(conn)
    subs = {
        r["id"]: r["strategy_name"]
        for r in conn.execute("SELECT id, strategy_name FROM sub_strategies ORDER BY id")
    }

    rows = conn.execute(
        """
        SELECT o.match_id, o.strategy_id, o.home_win_prob, o.draw_prob, o.away_win_prob,
               m.score_home, m.score_away
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        WHERE m.match_status = 'Завершен'
        """
    ).fetchall()

    accuracy = defaultdict(lambda: {"n": 0, "hits": 0, "by_thr": defaultdict(lambda: {"n": 0, "hits": 0})})
    real_roi = defaultdict(list)

    for r in rows:
        probs = {
            "1": (r["home_win_prob"] or 0) / 100.0,
            "X": (r["draw_prob"] or 0) / 100.0,
            "2": (r["away_win_prob"] or 0) / 100.0,
        }
        if sum(probs.values()) < 0.05:
            continue
        sel = max(probs, key=probs.get)
        p = probs[sel]
        hit = settle_1x2(r["score_home"], r["score_away"]) == sel
        acc = accuracy[r["strategy_id"]]
        acc["n"] += 1
        acc["hits"] += int(hit)
        for thr in (0.40, 0.45, 0.50, 0.55, 0.60):
            if p >= thr:
                acc["by_thr"][thr]["n"] += 1
                acc["by_thr"][thr]["hits"] += int(hit)
        market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
        o = odds_idx.get(r["match_id"], {}).get(market)
        if o:
            real_roi[r["strategy_id"]].append({"result": hit, "odds": o, "prob": p})

    acc_table = []
    for sid, a in accuracy.items():
        row = {
            "strategy": subs[sid],
            "n": a["n"],
            "winrate_pct": round(a["hits"] / a["n"] * 100, 2) if a["n"] else None,
            "thresholds": {
                str(thr): {
                    "n": v["n"],
                    "winrate_pct": round(v["hits"] / v["n"] * 100, 2) if v["n"] else None,
                }
                for thr, v in sorted(a["by_thr"].items())
                if v["n"] >= 15
            },
            "real_odds_roi": summarize(real_roi[sid]) if real_roi[sid] else None,
        }
        acc_table.append(row)
    acc_table.sort(key=lambda x: -(x["winrate_pct"] or 0))

    report = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    report["substrategy_accuracy_honest"] = acc_table
    # Remove misleading assumed-odds ROI blocks from verdict path
    report.pop("substrategy_flat_maxprob", None)
    report.pop("substrategy_by_threshold", None)

    main = report.get("main_prediction", {})
    by_sel = main.get("by_selection_real_odds", {})
    p1 = by_sel.get("1") or report.get("filtered_main_strategies", {}).get("П1_all")

    best_acc = acc_table[0] if acc_table else None
    finished = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE match_status='Завершен'"
    ).fetchone()[0]
    with_1x2 = conn.execute(
        """
        SELECT COUNT(DISTINCT m.match_id)
        FROM matches m
        JOIN odds o ON o.match_id = m.match_id AND o.market_name = '1X2_1'
        WHERE m.match_status = 'Завершен'
        """
    ).fetchone()[0]

    five_p = next((r for r in acc_table if r["strategy"] == "5Match p"), None)
    five = next((r for r in acc_table if r["strategy"] == "5Match"), None)

    report["verdict"] = {
        "best_validated_strategy": {
            "name": "matches.prediction = П1 (NTB home win)",
            **(p1 or {}),
            "note": "Фильтр по основному NTB-прогнозу; сверять с актуальным sample",
        },
        "best_substrategy_by_accuracy": best_acc,
        "five_match": {
            "5Match p": five_p,
            "5Match": five,
        },
        "avoid": [
            "mill",
            "ставки на все прогнозы подряд без фильтра",
            "5Match / 5Match p без порога вероятности (ROI около нуля / отрицательный)",
        ],
        "recommendation": [
            f"Результаты: {finished} завершённых матчей, 1X2 кэфы у {with_1x2} из них (канон 1X2_1/X/2).",
            f"5Match p: WR={five_p and five_p['winrate_pct']}%, "
            f"ROI={(five_p or {}).get('real_odds_roi') and five_p['real_odds_roi'].get('roi_pct')}% "
            f"на {(five_p or {}).get('real_odds_roi') and five_p['real_odds_roi'].get('bets')} ставках.",
            f"5Match: WR={five and five['winrate_pct']}%, "
            f"ROI={(five or {}).get('real_odds_roi') and five['real_odds_roi'].get('roi_pct')}% "
            f"на {(five or {}).get('real_odds_roi') and five['real_odds_roi'].get('bets')} ставках.",
            "Лучшая accuracy среди подстратегий — см. best_substrategy_by_accuracy; "
            "для value смотреть ROI при пороге p≥0.55–0.60.",
        ],
        "sample": {
            "finished_matches": finished,
            "finished_with_1x2": with_1x2,
            "main_pred_bets_real_odds": (main.get("real_odds_only") or {}).get("bets"),
            "substrategy_finished_rows": acc_table[0]["n"] if acc_table else 0,
        },
    }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ACCURACY:")
    for r in acc_table:
        print(f"  {r['strategy']}: n={r['n']} WR={r['winrate_pct']} thr={r['thresholds']} real={r['real_odds_roi']}")
    print("VERDICT:", report["verdict"]["recommendation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
