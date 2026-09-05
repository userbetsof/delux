"""Отдельный бэктест подстратегии mill за последние N матчей."""
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

from scripts.analyze_strategy_profit import load_odds_index, settle_1x2, summarize  # noqa: E402

OUT = ROOT / "data" / "mill_last400_report.json"
MILL_NAME = "mill"
THRESHOLDS = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
ODDS_BANDS = (
    ("1.01-1.50", 1.01, 1.50),
    ("1.50-2.00", 1.50, 2.00),
    ("2.00-2.50", 2.00, 2.50),
    ("2.50-3.50", 2.50, 3.50),
    ("3.50-5.00", 3.50, 5.00),
    ("5.00+", 5.00, 999.0),
)


def resolve_mill_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM sub_strategies WHERE LOWER(strategy_name)=? LIMIT 1",
        (MILL_NAME,),
    ).fetchone()
    if not row:
        raise SystemExit("sub_strategies: mill not found")
    return int(row[0])


def load_last_mill_matches(conn: sqlite3.Connection, mill_id: int, limit: int):
    return conn.execute(
        """
        SELECT
            o.match_id, o.home_win_prob, o.draw_prob, o.away_win_prob,
            m.score_home, m.score_away, m.match_date, m.sport, m.prediction,
            l.name AS league_name
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        LEFT JOIN leagues l ON l.id = m.league_id
        WHERE o.strategy_id = ?
          AND m.match_status = 'Завершен'
          AND (
            COALESCE(o.home_win_prob, 0)
            + COALESCE(o.draw_prob, 0)
            + COALESCE(o.away_win_prob, 0)
          ) >= 5
        ORDER BY m.match_date DESC, m.match_id DESC
        LIMIT ?
        """,
        (mill_id, limit),
    ).fetchall()


def pack_bets(rows, odds_idx):
    bets = []
    for r in rows:
        probs = {
            "1": (r["home_win_prob"] or 0) / 100.0,
            "X": (r["draw_prob"] or 0) / 100.0,
            "2": (r["away_win_prob"] or 0) / 100.0,
        }
        sel = max(probs, key=probs.get)
        p = probs[sel]
        actual = settle_1x2(r["score_home"], r["score_away"])
        hit = actual == sel
        market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
        odds = odds_idx.get(r["match_id"], {}).get(market)
        bets.append(
            {
                "match_id": r["match_id"],
                "match_date": r["match_date"],
                "sport": r["sport"],
                "league": r["league_name"],
                "score": f"{r['score_home']}:{r['score_away']}",
                "sel": sel,
                "prob": round(p, 4),
                "probs": {k: round(v, 4) for k, v in probs.items()},
                "hit": hit,
                "odds": odds,
                "ntb_prediction": r["prediction"],
            }
        )
    return bets


def by_key(bets, key_fn, with_odds_only=False):
    groups = defaultdict(list)
    for b in bets:
        if with_odds_only and not b["odds"]:
            continue
        groups[key_fn(b)].append(
            {"result": b["hit"], "odds": b["odds"]} if with_odds_only else b
        )
    out = {}
    for k, items in groups.items():
        if with_odds_only:
            out[k] = summarize(items)
        else:
            n = len(items)
            hits = sum(1 for x in items if x["hit"])
            with_o = [x for x in items if x["odds"]]
            out[k] = {
                "n": n,
                "winrate_pct": round(hits / n * 100, 2) if n else None,
                "real_odds_roi": summarize(
                    [{"result": x["hit"], "odds": x["odds"]} for x in with_o]
                )
                if with_o
                else None,
            }
    return dict(sorted(out.items(), key=lambda kv: -(kv[1].get("bets") or kv[1].get("n") or 0)))


def threshold_stats(bets):
    out = {}
    for thr in THRESHOLDS:
        subset = [b for b in bets if b["prob"] >= thr]
        with_o = [b for b in subset if b["odds"]]
        n = len(subset)
        hits = sum(1 for b in subset if b["hit"])
        out[str(thr)] = {
            "n": n,
            "winrate_pct": round(hits / n * 100, 2) if n else None,
            "real_odds_roi": summarize(
                [{"result": b["hit"], "odds": b["odds"]} for b in with_o]
            )
            if with_o
            else None,
        }
    return out


def odds_band_stats(bets):
    out = {}
    for label, lo, hi in ODDS_BANDS:
        subset = [
            b
            for b in bets
            if b["odds"] is not None and lo <= b["odds"] < hi
        ]
        if not subset:
            continue
        out[label] = summarize(
            [{"result": b["hit"], "odds": b["odds"]} for b in subset]
        )
    return out


def main() -> int:
    limit = 400
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])

    conn = sqlite3.connect("matches.db")
    conn.row_factory = sqlite3.Row
    mill_id = resolve_mill_id(conn)
    odds_idx = load_odds_index(conn)
    rows = load_last_mill_matches(conn, mill_id, limit)
    bets = pack_bets(rows, odds_idx)

    with_odds = [b for b in bets if b["odds"]]
    hits = sum(1 for b in bets if b["hit"])
    flat = summarize([{"result": b["hit"], "odds": b["odds"]} for b in with_odds])

    # chronological for cumulative (oldest → newest within window)
    chrono = sorted(bets, key=lambda b: (b["match_date"] or "", b["match_id"]))
    cum_profit = 0.0
    curve = []
    for i, b in enumerate(chrono, 1):
        if b["odds"]:
            cum_profit += (b["odds"] - 1) if b["hit"] else -1.0
        if i % 25 == 0 or i == len(chrono):
            curve.append({"n": i, "cum_profit": round(cum_profit, 2)})

    dates = [b["match_date"] for b in bets if b["match_date"]]
    report = {
        "strategy": MILL_NAME,
        "strategy_id": mill_id,
        "window": {
            "requested": limit,
            "actual": len(bets),
            "with_odds": len(with_odds),
            "date_from": min(dates) if dates else None,
            "date_to": max(dates) if dates else None,
        },
        "flat_maxprob": {
            "n": len(bets),
            "hits": hits,
            "winrate_pct": round(hits / len(bets) * 100, 2) if bets else None,
            "real_odds_roi": flat,
        },
        "by_selection": by_key(bets, lambda b: b["sel"]),
        "by_threshold": threshold_stats(bets),
        "by_odds_band": odds_band_stats(bets),
        "by_sport": by_key(bets, lambda b: str(b["sport"] or "")),
        "equity_curve_every_25": curve,
        "note": (
            "Окно: последние N завершённых матчей с ненулевыми вероятностями mill, "
            "сортировка по match_date DESC. Ставка flat 1 у.е. на исход с max p."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"mill last {limit}: n={len(bets)} with_odds={len(with_odds)}")
    print(f"  WR={report['flat_maxprob']['winrate_pct']}% ROI={flat and flat['roi_pct']}% profit={flat and flat['profit']}")
    print("  by selection:")
    for sel, s in report["by_selection"].items():
        roi = (s.get("real_odds_roi") or {}).get("roi_pct")
        print(f"    {sel}: n={s['n']} WR={s['winrate_pct']}% ROI={roi}")
    print("  by threshold:")
    for thr, s in report["by_threshold"].items():
        roi = (s.get("real_odds_roi") or {}).get("roi_pct")
        print(f"    p>={thr}: n={s['n']} WR={s['winrate_pct']}% ROI={roi}")
    print("  by odds band:")
    for band, s in report["by_odds_band"].items():
        print(f"    {band}: n={s['bets']} WR={s['winrate_pct']}% ROI={s['roi_pct']}%")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
