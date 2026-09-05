"""Edge analysis without settled scores + optional result backfill."""
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

from scripts.analyze_strategy_profit import (  # noqa: E402
    ASSUMED_ODDS,
    load_odds_index,
    normalize_pred,
    odds_for,
    summarize,
    to_float,
)

OUT = ROOT / "data" / "strategy_profit_report.json"


def main():
    conn = sqlite3.connect("matches.db")
    conn.row_factory = sqlite3.Row
    odds_idx = load_odds_index(conn)

    matches = conn.execute(
        """
        SELECT match_id, sport, match_date, prediction, match_status,
               score_home, score_away
        FROM matches
        """
    ).fetchall()

    finished = [
        m
        for m in matches
        if m["match_status"] in ("Завершен", "После овертайма", "После буллитов")
        or (
            m["score_home"] is not None
            and m["score_away"] is not None
            and not (m["score_home"] == 0 and m["score_away"] == 0)
        )
    ]

    # --- prediction inventory ---
    pred_counts = defaultdict(int)
    with_odds = defaultdict(int)
    edges = defaultdict(list)  # label -> list of edge = prob_implied inverse

    for m in matches:
        info = normalize_pred(m["prediction"])
        if not info or info["kind"] == "unknown":
            if m["prediction"]:
                pred_counts[str(m["prediction"])] += 1
            continue
        pred_counts[info["label"]] += 1
        markets = odds_idx.get(m["match_id"], {})
        o = odds_for(info, markets, assume=False)
        if o:
            with_odds[info["label"]] += 1
            edges[info["label"]].append(
                {
                    "match_id": m["match_id"],
                    "odds": o,
                    "implied_prob": round(1 / o, 4),
                    "sport": m["sport"],
                    "date": m["match_date"],
                }
            )

    # --- substrategy edges vs book odds ---
    subs = {
        r["id"]: r["strategy_name"]
        for r in conn.execute("SELECT id, strategy_name FROM sub_strategies")
    }
    sub_rows = conn.execute(
        """
        SELECT o.match_id, o.strategy_id, o.home_win_prob, o.draw_prob, o.away_win_prob, m.sport
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        """
    ).fetchall()

    thr_edge_stats = {}
    for thr in (0.40, 0.45, 0.50, 0.55, 0.60):
        for min_edge in (1.00, 1.05, 1.10, 1.15, 1.20):
            key = f"p>={thr:.2f}_edge>={min_edge:.2f}"
            by_sub = defaultdict(list)
            for r in sub_rows:
                probs = {
                    "1": (r["home_win_prob"] or 0) / 100.0,
                    "X": (r["draw_prob"] or 0) / 100.0,
                    "2": (r["away_win_prob"] or 0) / 100.0,
                }
                if sum(probs.values()) < 0.05:
                    continue
                sel = max(probs, key=probs.get)
                p = probs[sel]
                if p < thr:
                    continue
                market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
                odds = odds_idx.get(r["match_id"], {}).get(market)
                if not odds:
                    continue
                edge = p * odds
                if edge < min_edge:
                    continue
                by_sub[r["strategy_id"]].append(
                    {
                        "sel": sel,
                        "prob": round(p, 4),
                        "odds": odds,
                        "edge": round(edge, 3),
                        "sport": r["sport"],
                        "match_id": r["match_id"],
                    }
                )
            thr_edge_stats[key] = {}
            for sid, bets in by_sub.items():
                if len(bets) < 15:
                    continue
                avg_edge = sum(b["edge"] for b in bets) / len(bets)
                avg_odds = sum(b["odds"] for b in bets) / len(bets)
                avg_prob = sum(b["prob"] for b in bets) / len(bets)
                thr_edge_stats[key][subs[sid]] = {
                    "candidates": len(bets),
                    "avg_model_prob": round(avg_prob, 4),
                    "avg_odds": round(avg_odds, 3),
                    "avg_edge": round(avg_edge, 3),
                    "unique_matches": len({b["match_id"] for b in bets}),
                    "sel_mix": {
                        s: sum(1 for b in bets if b["sel"] == s) for s in ("1", "X", "2")
                    },
                }

    # Rank by avg_edge * sqrt(n) as proxy quality (no settlement)
    ranked = []
    for cfg, items in thr_edge_stats.items():
        for name, s in items.items():
            ranked.append(
                {
                    "config": cfg,
                    "strategy": name,
                    "score": round(s["avg_edge"] * (s["candidates"] ** 0.5), 2),
                    **s,
                }
            )
    ranked.sort(key=lambda x: x["score"], reverse=True)

    # How often each sub has non-zero probs
    sub_nonzero = defaultdict(int)
    sub_total = defaultdict(int)
    for r in sub_rows:
        sub_total[r["strategy_id"]] += 1
        if ((r["home_win_prob"] or 0) + (r["draw_prob"] or 0) + (r["away_win_prob"] or 0)) > 1:
            sub_nonzero[r["strategy_id"]] += 1

    coverage = {
        subs[sid]: {
            "rows": sub_total[sid],
            "nonzero": sub_nonzero[sid],
            "nonzero_pct": round(sub_nonzero[sid] / sub_total[sid] * 100, 1) if sub_total[sid] else 0,
        }
        for sid in subs
    }

    # Date range
    dates = [m["match_date"] for m in matches if m["match_date"]]
    dates_sorted = sorted(dates)

    report = {
        "source": str(ROOT / "matches.db"),
        "data_quality": {
            "matches_total": len(matches),
            "matches_finished_usable": len(finished),
            "all_status_not_started": all(m["match_status"] == "Не начался" for m in matches),
            "all_scores_0_0": all(
                (m["score_home"] or 0) == 0 and (m["score_away"] or 0) == 0 for m in matches
            ),
            "date_min": dates_sorted[0] if dates_sorted else None,
            "date_max": dates_sorted[-1] if dates_sorted else None,
            "blocker": (
                "В matches все 915 матчей имеют status='Не начался' и score 0:0. "
                "Без реальных результатов ROI/profit посчитать нельзя — только анализ edge "
                "(модельная вероятность × коэффициент)."
            ),
        },
        "prediction_inventory": {
            "counts": dict(sorted(pred_counts.items(), key=lambda x: -x[1])),
            "with_real_odds": dict(sorted(with_odds.items(), key=lambda x: -x[1])),
        },
        "substrategy_coverage": coverage,
        "value_candidates_no_settlement": {
            "top_20": ranked[:20],
            "note": (
                "Это НЕ прибыль. Это сигналы, где модель считает исход вероятнее, "
                "чем подразумевает линия. Нужен backfill результатов для проверки."
            ),
        },
        "next_steps": [
            "Заполнить score_home/score_away и match_status через result checker / Flashscore detail feed",
            "Повторить scripts/analyze_strategy_profit.py на завершённых матчах",
            "Отдельно валидировать подстратегии с ненулевым coverage (mill, Mini Vini и т.д.)",
        ],
    }

    # If somehow finished exist — full settle
    if finished:
        report["settled_backtest_available"] = True
    else:
        report["settled_backtest_available"] = False

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["data_quality"], ensure_ascii=False, indent=2))
    print("coverage:", json.dumps(coverage, ensure_ascii=False, indent=2))
    print("top value candidates:")
    for row in ranked[:12]:
        print(
            f"  {row['strategy']:12} {row['config']}: n={row['candidates']} "
            f"avg_edge={row['avg_edge']} avg_odds={row['avg_odds']} score={row['score']}"
        )
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
