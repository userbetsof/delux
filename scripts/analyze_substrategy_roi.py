"""Substrategy accuracy + ROI (assumed odds if missing) on finished matches."""
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
    settle_1x2,
    summarize,
)

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
               m.score_home, m.score_away, m.sport
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        WHERE m.match_status = 'Завершен'
        """
    ).fetchall()

    # Flat: always bet max-prob outcome
    by_sub_flat = defaultdict(list)
    by_sub_thr = {thr: defaultdict(list) for thr in (0.40, 0.45, 0.50, 0.55, 0.60)}
    by_sub_value = {edge: defaultdict(list) for edge in (1.0, 1.05, 1.10)}

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
        actual = settle_1x2(r["score_home"], r["score_away"])
        market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
        o_real = odds_idx.get(r["match_id"], {}).get(market)
        o_use = o_real or ASSUMED_ODDS[sel]
        bet = {
            "result": actual == sel,
            "odds": o_use,
            "prob": p,
            "sel": sel,
            "used_assumed": o_real is None,
            "sport": r["sport"],
            "match_id": r["match_id"],
        }
        by_sub_flat[r["strategy_id"]].append(bet)
        for thr, bucket in by_sub_thr.items():
            if p >= thr:
                bucket[r["strategy_id"]].append(bet)
        if o_real:
            for edge, bucket in by_sub_value.items():
                if p * o_real >= edge:
                    bucket[r["strategy_id"]].append({**bet, "odds": o_real})

    def pack(buckets, min_n=20):
        out = {}
        for sid, bets in buckets.items():
            s = summarize(bets)
            if s["bets"] < min_n:
                continue
            assumed_n = sum(1 for b in bets if b.get("used_assumed"))
            out[subs[sid]] = {**s, "assumed_odds_bets": assumed_n}
        return dict(sorted(out.items(), key=lambda x: -(x[1]["roi_pct"] or -999)))

    flat = pack(by_sub_flat)
    thr_packs = {f"p>={thr}": pack(b) for thr, b in by_sub_thr.items()}
    value_packs = {
        f"real_odds_edge>={e}": pack(b, min_n=5) for e, b in by_sub_value.items()
    }

    # Main prediction filters: П1 only, min odds, etc.
    main_rows = conn.execute(
        """
        SELECT match_id, prediction, score_home, score_away, sport
        FROM matches
        WHERE match_status='Завершен'
          AND prediction IS NOT NULL AND TRIM(prediction) NOT IN ('','-')
        """
    ).fetchall()

    from scripts.analyze_strategy_profit import normalize_pred, settle, odds_for

    filters = {}
    # П1 only with odds>=1.5 and <=2.2
    for name, pred_filter, odds_lo, odds_hi in (
        ("П1_all", lambda i: i and i.get("label") == "1", 1.01, 10),
        ("П1_odds_1.50-2.10", lambda i: i and i.get("label") == "1", 1.50, 2.10),
        ("П1_odds_1.60-2.00", lambda i: i and i.get("label") == "1", 1.60, 2.00),
        ("П2_all", lambda i: i and i.get("label") == "2", 1.01, 10),
        ("П2_odds_1.50-2.20", lambda i: i and i.get("label") == "2", 1.50, 2.20),
        ("1X_all", lambda i: i and i.get("label") == "1X", 1.01, 10),
        ("X2_all", lambda i: i and i.get("label") == "X2", 1.01, 10),
        ("DC_only_1X_X2", lambda i: i and i.get("label") in ("1X", "X2"), 1.01, 10),
    ):
        bets = []
        for m in main_rows:
            info = normalize_pred(m["prediction"])
            if not pred_filter(info):
                continue
            result = settle(info, m["score_home"], m["score_away"])
            if result is None:
                continue
            o = odds_for(info, odds_idx.get(m["match_id"], {}), assume=True)
            if not o or o < odds_lo or o > odds_hi:
                continue
            bets.append({"result": result, "odds": o})
        filters[name] = summarize(bets)

    # Combine: П1 when Mini Vini also picks 1 with p>=0.45
    combo_bets = []
    mini_vini_id = [k for k, v in subs.items() if v == "Mini Vini"][0]
    mv = {
        r["match_id"]: r
        for r in conn.execute(
            "SELECT match_id, home_win_prob, draw_prob, away_win_prob FROM outcome_probabilities WHERE strategy_id=?",
            (mini_vini_id,),
        )
    }
    for m in main_rows:
        info = normalize_pred(m["prediction"])
        if not info or info.get("label") != "1":
            continue
        op = mv.get(m["match_id"])
        if not op:
            continue
        p1 = (op["home_win_prob"] or 0) / 100.0
        if p1 < 0.45:
            continue
        result = settle(info, m["score_home"], m["score_away"])
        o = odds_for(info, odds_idx.get(m["match_id"], {}), assume=True)
        if not o:
            continue
        combo_bets.append({"result": result, "odds": o, "prob": p1})
    filters["П1 + MiniVini_p1>=0.45"] = summarize(combo_bets)

    # Load existing report and merge
    report = {}
    if OUT.exists():
        report = json.loads(OUT.read_text(encoding="utf-8"))

    report["settled_matches"] = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE match_status='Завершен'"
    ).fetchone()[0]
    report["substrategy_flat_maxprob"] = flat
    report["substrategy_by_threshold"] = thr_packs
    report["substrategy_value_real_odds"] = value_packs
    report["filtered_main_strategies"] = filters

    # Verdict
    best_filter = max(
        ((k, v) for k, v in filters.items() if v.get("bets", 0) >= 25 and v.get("roi_pct") is not None),
        key=lambda x: x[1]["roi_pct"],
        default=(None, None),
    )
    best_sub = max(
        ((k, v) for k, v in flat.items() if v.get("bets", 0) >= 50),
        key=lambda x: x[1]["roi_pct"],
        default=(None, None),
    )
    best_thr = None
    best_thr_roi = -999
    for cfg, items in thr_packs.items():
        for name, s in items.items():
            if s["bets"] >= 40 and (s["roi_pct"] or -999) > best_thr_roi:
                best_thr_roi = s["roi_pct"]
                best_thr = {"config": cfg, "strategy": name, **s}

    report["verdict"] = {
        "best_filtered_main": {"name": best_filter[0], **best_filter[1]} if best_filter[0] else None,
        "best_substrategy_flat": {"name": best_sub[0], **best_sub[1]} if best_sub[0] else None,
        "best_substrategy_thresholded": best_thr,
        "overall_main_real_odds": report.get("main_prediction", {}).get("real_odds_only"),
        "recommendation": None,
    }

    # Build recommendation text
    rec = []
    if best_filter[0] and best_filter[1]["roi_pct"] > 0:
        rec.append(
            f"Лучший фильтр основного прогноза: {best_filter[0]} "
            f"(n={best_filter[1]['bets']}, ROI={best_filter[1]['roi_pct']}%, WR={best_filter[1]['winrate_pct']}%)"
        )
    if best_thr and best_thr["roi_pct"] > 0:
        rec.append(
            f"Лучшая подстратегия: {best_thr['strategy']} при {best_thr['config']} "
            f"(n={best_thr['bets']}, ROI={best_thr['roi_pct']}%)"
        )
    if not rec:
        rec.append(
            "Устойчиво прибыльной стратегии на текущей выборке нет; "
            "ближе всего к нулю — ставки на П1 из matches.prediction."
        )
    report["verdict"]["recommendation"] = rec

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("FLAT SUBSTRATEGIES:")
    for k, v in list(flat.items())[:10]:
        print(f"  {k}: n={v['bets']} WR={v['winrate_pct']} ROI={v['roi_pct']} assumed={v['assumed_odds_bets']}")
    print("\nTHRESHOLDS:")
    for cfg, items in thr_packs.items():
        if not items:
            continue
        top = next(iter(items.items()))
        print(f"  {cfg} best {top[0]}: n={top[1]['bets']} WR={top[1]['winrate_pct']} ROI={top[1]['roi_pct']}")
    print("\nFILTERS:")
    for k, v in filters.items():
        print(f"  {k}: {v}")
    print("\nVERDICT:", report["verdict"]["recommendation"])
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
