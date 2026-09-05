"""Совпадение сигналов 1 пр и poisson на завершённых матчах."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"c:\papki\work\bets\delux")
DB = ROOT / "matches.db"
OUT = ROOT / "data" / "onepr_poisson_agree.json"


def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        try:
            return float(str(v).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None


def settle(h, a):
    if h > a:
        return "1"
    if h < a:
        return "2"
    return "X"


def summarize(bets):
    n = wins = 0
    staked = returned = odds_sum = 0.0
    for b in bets:
        odds = float(b["odds"])
        n += 1
        staked += 1
        odds_sum += odds
        if b["hit"]:
            wins += 1
            returned += odds
    profit = returned - staked
    return {
        "bets": n,
        "wins": wins,
        "losses": n - wins,
        "winrate_pct": round(wins / n * 100, 2) if n else None,
        "avg_odds": round(odds_sum / n, 3) if n else None,
        "profit": round(profit, 2),
        "roi_pct": round(profit / staked * 100, 2) if staked else None,
    }


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    ids = {
        r["strategy_name"]: r["id"]
        for r in conn.execute("SELECT id, strategy_name FROM sub_strategies")
    }
    sid_1 = ids["1 пр"]
    sid_p = ids["poisson"]

    rows = conn.execute(
        """
        SELECT m.match_id, m.score_home, m.score_away, m.match_date,
               o1.home_win_prob AS h1, o1.draw_prob AS d1, o1.away_win_prob AS a1,
               op.home_win_prob AS hp, op.draw_prob AS dp, op.away_win_prob AS ap
        FROM matches m
        JOIN outcome_probabilities o1 ON o1.match_id=m.match_id AND o1.strategy_id=?
        JOIN outcome_probabilities op ON op.match_id=m.match_id AND op.strategy_id=?
        WHERE m.match_status='Завершен'
          AND COALESCE(o1.home_win_prob,0)+COALESCE(o1.draw_prob,0)+COALESCE(o1.away_win_prob,0) >= 5
          AND COALESCE(op.home_win_prob,0)+COALESCE(op.draw_prob,0)+COALESCE(op.away_win_prob,0) >= 5
        ORDER BY m.match_date
        """,
        (sid_1, sid_p),
    ).fetchall()

    odds_idx = defaultdict(dict)
    for r in conn.execute(
        """
        SELECT match_id, market_name, odds_value FROM odds
        WHERE UPPER(market_name) IN ('1X2_1','1X2_X','1X2_2') AND odds_value IS NOT NULL
        """
    ):
        ov = to_float(r["odds_value"])
        if not ov or ov <= 1:
            continue
        k = str(r["market_name"]).upper()
        prev = odds_idx[r["match_id"]].get(k)
        if prev is None or ov > prev:
            odds_idx[r["match_id"]][k] = ov

    def pick(h, d, a):
        probs = {"1": (h or 0) / 100.0, "X": (d or 0) / 100.0, "2": (a or 0) / 100.0}
        sel = max(probs, key=probs.get)
        return sel, probs[sel], probs

    agree = disagree = 0
    agree_bets = []
    by_sel = defaultdict(list)
    by_thr = {t: [] for t in (0.40, 0.45, 0.50, 0.55, 0.60)}
    both_alone = []  # agree vs each alone on same matches

    for r in rows:
        s1, p1, pr1 = pick(r["h1"], r["d1"], r["a1"])
        sp, pp, prp = pick(r["hp"], r["dp"], r["ap"])
        actual = settle(r["score_home"], r["score_away"])
        if s1 != sp:
            disagree += 1
            continue
        agree += 1
        hit = actual == s1
        p_avg = (p1 + pp) / 2
        market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[s1]
        odds = odds_idx.get(r["match_id"], {}).get(market)
        item = {
            "match_id": r["match_id"],
            "sel": s1,
            "p1": round(p1, 4),
            "pp": round(pp, 4),
            "p_avg": round(p_avg, 4),
            "p_min": round(min(p1, pp), 4),
            "hit": hit,
            "odds": odds,
        }
        agree_bets.append(item)
        by_sel[s1].append(item)
        for thr in by_thr:
            if min(p1, pp) >= thr:
                by_thr[thr].append(item)

    with_odds = [b for b in agree_bets if b["odds"]]
    report = {
        "universe": {
            "both_present": len(rows),
            "agree": agree,
            "disagree": disagree,
            "agree_pct": round(agree / len(rows) * 100, 2) if rows else None,
            "agree_with_odds": len(with_odds),
        },
        "agree_flat": {
            "n": agree,
            "winrate_pct": round(sum(1 for b in agree_bets if b["hit"]) / agree * 100, 2)
            if agree
            else None,
            "real_odds": summarize([{"hit": b["hit"], "odds": b["odds"]} for b in with_odds])
            if with_odds
            else None,
        },
        "by_selection": {},
        "by_min_prob": {},
        "baseline_same_sample": {},
    }

    for sel, items in by_sel.items():
        wo = [b for b in items if b["odds"]]
        report["by_selection"][sel] = {
            "n": len(items),
            "winrate_pct": round(sum(1 for b in items if b["hit"]) / len(items) * 100, 2),
            "real_odds": summarize([{"hit": b["hit"], "odds": b["odds"]} for b in wo])
            if wo
            else None,
        }

    for thr, items in by_thr.items():
        if len(items) < 10:
            continue
        wo = [b for b in items if b["odds"]]
        report["by_min_prob"][str(thr)] = {
            "n": len(items),
            "winrate_pct": round(sum(1 for b in items if b["hit"]) / len(items) * 100, 2),
            "real_odds": summarize([{"hit": b["hit"], "odds": b["odds"]} for b in wo])
            if wo
            else None,
        }

    # baselines: 1пр / poisson alone on the AGREE match set
    for name, key_p in (("1 пр", "p1"), ("poisson", "pp")):
        # rebuild picks on agree match_ids only — already have sel from agree
        # For fair compare: on same agree matches, each strategy's max-prob (always same sel when agree)
        wo = [b for b in agree_bets if b["odds"]]
        report["baseline_same_sample"][name] = {
            "note": "на тех же матчах, где оба выбрали один исход",
            "real_odds": summarize([{"hit": b["hit"], "odds": b["odds"]} for b in wo])
            if wo
            else None,
        }

    # Also: full-sample alone baselines for context
    def alone(sid, label):
        bets = []
        for r in conn.execute(
            """
            SELECT m.match_id, m.score_home, m.score_away,
                   o.home_win_prob, o.draw_prob, o.away_win_prob
            FROM outcome_probabilities o
            JOIN matches m ON m.match_id=o.match_id
            WHERE o.strategy_id=? AND m.match_status='Завершен'
              AND COALESCE(o.home_win_prob,0)+COALESCE(o.draw_prob,0)+COALESCE(o.away_win_prob,0)>=5
            """,
            (sid,),
        ):
            sel, p, _ = pick(r["home_win_prob"], r["draw_prob"], r["away_win_prob"])
            hit = settle(r["score_home"], r["score_away"]) == sel
            market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
            odds = odds_idx.get(r["match_id"], {}).get(market)
            if odds:
                bets.append({"hit": hit, "odds": odds, "p": p})
        return {"n_with_odds": len(bets), "real_odds": summarize(bets) if bets else None}

    report["baseline_full"] = {
        "1 пр": alone(sid_1, "1 пр"),
        "poisson": alone(sid_p, "poisson"),
    }

    # disagree sample: what if we still bet 1пр only / poisson only
    # already have counts

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
