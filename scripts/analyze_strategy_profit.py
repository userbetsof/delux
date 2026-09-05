"""Backtest DeluX strategies on matches.db → data/strategy_profit_report.json"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "matches.db"
OUT = ROOT / "data" / "strategy_profit_report.json"

ASSUMED_ODDS = {"1": 2.05, "X": 3.3, "2": 3.4, "1X": 1.45, "X2": 1.45, "12": 1.35}


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


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def settle_1x2(h, a):
    if h is None or a is None:
        return None
    if h > a:
        return "1"
    if h < a:
        return "2"
    return "X"


def normalize_pred(raw: str):
    if not raw:
        return None
    p = str(raw).strip()
    if p in ("-", "", "None"):
        return None
    u = p.upper().replace("Х", "X").replace("х", "X")
    u = u.replace("П1", "1").replace("П2", "2")
    u_compact = re.sub(r"\s+", "", u)

    if u_compact in ("1", "X", "2", "1X", "X2", "12"):
        return {"kind": "1x2", "sel": u_compact, "label": u_compact}

    if "ОЗ" in u or "BTTS" in u or "ОБЕЗАБ" in u_compact.replace("Ё", "Е"):
        # "Обе Забьют" / "ОЗ" → yes; "ОЗНет" rare
        no = "НЕТ" in u or "NO" in u
        return {"kind": "btts", "sel": "no" if no else "yes", "label": "BTTS_NO" if no else "BTTS_YES"}

    m = re.search(r"(ТБ|ТМ|OVER|UNDER)\s*([0-9]+(?:[.,][0-9]+)?)", u, re.I)
    if m:
        side = "over" if m.group(1).upper() in ("ТБ", "OVER") else "under"
        line = float(m.group(2).replace(",", "."))
        return {"kind": "ou", "side": side, "line": line, "label": f"{side}_{line}"}

    m = re.search(r"Ф([12])\s*\(([-+]?\d+(?:[.,]\d+)?)\)", u)
    if m:
        side = "home" if m.group(1) == "1" else "away"
        line = float(m.group(2).replace(",", "."))
        return {"kind": "ah", "side": side, "line": line, "label": f"ah_{side}_{line}"}

    # bare Ф1(0) etc already handled; Ф1 without line
    m = re.search(r"Ф([12])", u)
    if m:
        side = "home" if m.group(1) == "1" else "away"
        return {"kind": "ah", "side": side, "line": 0.0, "label": f"ah_{side}_0"}

    return {"kind": "unknown", "sel": p, "label": p}


def settle(info, h, a):
    if not info or h is None or a is None:
        return None
    kind = info["kind"]
    if kind == "1x2":
        res = settle_1x2(h, a)
        sel = info["sel"]
        mapping = {
            "1": res == "1",
            "2": res == "2",
            "X": res == "X",
            "1X": res in ("1", "X"),
            "X2": res in ("X", "2"),
            "12": res in ("1", "2"),
        }
        return mapping.get(sel)
    if kind == "btts":
        both = h > 0 and a > 0
        return both if info["sel"] == "yes" else (not both)
    if kind == "ou":
        total = h + a
        line = info["line"]
        if abs(line - round(line)) < 1e-9 and total == line:
            return "push"
        return total > line if info["side"] == "over" else total < line
    if kind == "ah":
        line = info["line"]
        adj = (h + line - a) if info["side"] == "home" else (a + line - h)
        if abs(adj) < 1e-9:
            return "push"
        return adj > 0
    return None


def summarize(bets):
    n = wins = pushes = 0
    staked = returned = 0.0
    odds_sum = 0.0
    for b in bets:
        r = b.get("result")
        if r is None:
            continue
        if r == "push":
            pushes += 1
            continue
        odds = float(b["odds"])
        stake = float(b.get("stake", 1.0))
        n += 1
        staked += stake
        odds_sum += odds
        if r is True:
            wins += 1
            returned += stake * odds
    profit = returned - staked
    return {
        "bets": n,
        "wins": wins,
        "losses": n - wins,
        "pushes": pushes,
        "winrate_pct": round(wins / n * 100, 2) if n else None,
        "avg_odds": round(odds_sum / n, 3) if n else None,
        "staked": round(staked, 2),
        "returned": round(returned, 2),
        "profit": round(profit, 2),
        "roi_pct": round(profit / staked * 100, 2) if staked else None,
    }


def load_odds_index(conn):
    """match_id -> market_name -> max odds_value; also flat 1X2 from wide columns."""
    idx = defaultdict(dict)
    for r in conn.execute(
        """
        SELECT match_id, market_name, odds_value
        FROM odds
        WHERE odds_value IS NOT NULL AND market_name IS NOT NULL
        """
    ):
        ov = to_float(r["odds_value"])
        if not ov or ov <= 1:
            continue
        key = str(r["market_name"]).upper()
        prev = idx[r["match_id"]].get(key)
        if prev is None or ov > prev:
            idx[r["match_id"]][key] = ov

    # wide columns (older format) — MAX() fails on mixed text, scan rows
    for r in conn.execute(
        """
        SELECT match_id, home_win_odds, draw_odds, away_win_odds,
               odds_1x, odds_12, odds_2x
        FROM odds
        WHERE home_win_odds IS NOT NULL
           OR draw_odds IS NOT NULL
           OR away_win_odds IS NOT NULL
           OR odds_1x IS NOT NULL
           OR odds_12 IS NOT NULL
           OR odds_2x IS NOT NULL
        """
    ):
        m = idx[r["match_id"]]
        for col, key in (
            ("home_win_odds", "1X2_1"),
            ("draw_odds", "1X2_X"),
            ("away_win_odds", "1X2_2"),
            ("odds_1x", "DC_1X"),
            ("odds_12", "DC_12"),
            ("odds_2x", "DC_X2"),
        ):
            ov = to_float(r[col])
            if ov and ov > 1 and (key not in m or ov > m[key]):
                m[key] = ov

    # Derive double-chance from 1X2 when DC markets missing
    for mid, m in idx.items():
        o1, ox, o2 = m.get("1X2_1"), m.get("1X2_X"), m.get("1X2_2")
        if not (o1 and ox and o2):
            continue
        inv1, invx, inv2 = 1 / o1, 1 / ox, 1 / o2
        s = inv1 + invx + inv2
        if s <= 0:
            continue
        derived = {
            "DC_1X": s / (inv1 + invx),
            "DC_12": s / (inv1 + inv2),
            "DC_X2": s / (invx + inv2),
        }
        for k, v in derived.items():
            if k not in m and v > 1:
                m[k] = round(v, 3)
    return idx


def odds_for(info, markets: dict, assume=False):
    if not info:
        return None
    kind = info["kind"]
    if kind == "1x2":
        key = {
            "1": "1X2_1",
            "X": "1X2_X",
            "2": "1X2_2",
            "1X": "DC_1X",
            "12": "DC_12",
            "X2": "DC_X2",
        }[info["sel"]]
        if key in markets:
            return markets[key]
        return ASSUMED_ODDS.get(info["sel"]) if assume else None
    if kind == "btts":
        key = "BTTS_YES" if info["sel"] == "yes" else "BTTS_NO"
        return markets.get(key)
    if kind == "ou":
        prefix = "OVER" if info["side"] == "over" else "UNDER"
        line = info["line"]
        # exact
        for name, ov in markets.items():
            if name.startswith(prefix + " ") and "HALF" not in name:
                try:
                    if abs(float(name.split()[-1].replace(",", ".")) - line) < 1e-6:
                        return ov
                except ValueError:
                    pass
        return None
    if kind == "ah":
        side = "HOME" if info["side"] == "home" else "AWAY"
        line = info["line"]
        for name, ov in markets.items():
            if name.startswith(f"HANDICAP {side}"):
                try:
                    if abs(float(name.split()[-1].replace(",", ".")) - line) < 1e-6:
                        return ov
                except ValueError:
                    pass
        return None
    return None


def main():
    conn = connect()
    odds_idx = load_odds_index(conn)

    matches = conn.execute(
        """
        SELECT match_id, sport, match_date, prediction, score_home, score_away, match_status
        FROM matches
        WHERE match_status IN ('Завершен', 'После овертайма', 'После буллитов')
        """
    ).fetchall()

    matches = list(matches)

    strategies = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM strategies")}
    subs = {r["id"]: r["strategy_name"] for r in conn.execute("SELECT id, strategy_name FROM sub_strategies ORDER BY id")}

    # --- 1) Main: matches.prediction ---
    main_bets_real = []
    main_bets_assume = []
    by_label_real = defaultdict(list)
    by_label_assume = defaultdict(list)
    by_sport = defaultdict(list)
    unknown = defaultdict(int)

    for m in matches:
        info = normalize_pred(m["prediction"])
        if not info:
            continue
        if info["kind"] == "unknown":
            unknown[info["label"]] += 1
            continue
        result = settle(info, m["score_home"], m["score_away"])
        if result is None:
            continue
        markets = odds_idx.get(m["match_id"], {})
        o_real = odds_for(info, markets, assume=False)
        o_ass = odds_for(info, markets, assume=True)
        base = {
            "match_id": m["match_id"],
            "sport": m["sport"],
            "prediction": m["prediction"],
            "label": info["label"],
            "result": result,
            "date": m["match_date"],
        }
        if o_real:
            bet = {**base, "odds": o_real}
            main_bets_real.append(bet)
            by_label_real[info["label"]].append(bet)
            by_sport[str(m["sport"])].append(bet)
        if o_ass:
            bet = {**base, "odds": o_ass}
            main_bets_assume.append(bet)
            by_label_assume[info["label"]].append(bet)

    # --- 2) strategy_predictions ---
    sp_by_strat = defaultdict(list)
    for r in conn.execute(
        """
        SELECT sp.match_id, sp.strategy_id, sp.prediction, m.score_home, m.score_away, m.sport
        FROM strategy_predictions sp
        JOIN matches m ON m.match_id = sp.match_id
        WHERE m.match_status IN ('Завершен', 'После овертайма', 'После буллитов')
        """
    ):
        info = normalize_pred(r["prediction"])
        if not info or info["kind"] == "unknown":
            continue
        result = settle(info, r["score_home"], r["score_away"])
        if result is None:
            continue
        markets = odds_idx.get(r["match_id"], {})
        odds = odds_for(info, markets, assume=True)
        if not odds:
            continue
        name = strategies.get(r["strategy_id"], str(r["strategy_id"]))
        sp_by_strat[name].append(
            {
                "match_id": r["match_id"],
                "sport": r["sport"],
                "prediction": r["prediction"],
                "label": info["label"],
                "result": result,
                "odds": odds,
            }
        )

    # --- 3) Sub-strategy model probabilities vs 1X2 odds ---
    sub_rows = conn.execute(
        """
        SELECT o.match_id, o.strategy_id, o.home_win_prob, o.draw_prob, o.away_win_prob,
               m.score_home, m.score_away, m.sport
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        WHERE m.match_status IN ('Завершен', 'После овертайма', 'После буллитов')
        """
    ).fetchall()

    sub_backtests = {}
    thresholds = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    edges = [1.00, 1.05, 1.10, 1.15]

    for thr in thresholds:
        for edge in edges:
            key = f"p>={thr:.2f}_edge>={edge:.2f}"
            buckets = defaultdict(list)
            for r in sub_rows:
                probs = {
                    "1": (r["home_win_prob"] or 0) / 100.0,
                    "X": (r["draw_prob"] or 0) / 100.0,
                    "2": (r["away_win_prob"] or 0) / 100.0,
                }
                if sum(probs.values()) < 0.05:
                    continue
                sel = max(probs, key=probs.get)
                prob = probs[sel]
                if prob < thr:
                    continue
                market = {"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel]
                odds = odds_idx.get(r["match_id"], {}).get(market)
                if not odds:
                    continue
                if prob * odds < edge:
                    continue
                actual = settle_1x2(r["score_home"], r["score_away"])
                buckets[r["strategy_id"]].append(
                    {
                        "match_id": r["match_id"],
                        "sport": r["sport"],
                        "sel": sel,
                        "prob": round(prob, 4),
                        "odds": odds,
                        "edge": round(prob * odds, 3),
                        "result": actual == sel,
                    }
                )
            sub_backtests[key] = {
                subs.get(sid, str(sid)): summarize(bets)
                for sid, bets in sorted(buckets.items())
                if len(bets) >= 20
            }

    # Rank all sub configs
    ranked_subs = []
    for cfg, items in sub_backtests.items():
        for name, s in items.items():
            if s["bets"] >= 30 and s["roi_pct"] is not None:
                ranked_subs.append({"config": cfg, "strategy": name, **s})
    ranked_subs.sort(key=lambda x: (x["roi_pct"], x["bets"]), reverse=True)

    # Consensus: average of non-zero sub probs
    consensus_bets = defaultdict(list)  # thr -> bets
    by_match_probs = defaultdict(list)
    for r in sub_rows:
        probs = (
            (r["home_win_prob"] or 0) / 100.0,
            (r["draw_prob"] or 0) / 100.0,
            (r["away_win_prob"] or 0) / 100.0,
        )
        if sum(probs) < 0.05:
            continue
        by_match_probs[r["match_id"]].append((probs, r["score_home"], r["score_away"], r["sport"]))

    for thr in (0.45, 0.50, 0.55):
        bets = []
        for mid, lst in by_match_probs.items():
            # average across strategies
            n = len(lst)
            h = sum(p[0][0] for p in lst) / n
            d = sum(p[0][1] for p in lst) / n
            a = sum(p[0][2] for p in lst) / n
            probs = {"1": h, "X": d, "2": a}
            sel = max(probs, key=probs.get)
            prob = probs[sel]
            if prob < thr:
                continue
            odds = odds_idx.get(mid, {}).get({"1": "1X2_1", "X": "1X2_X", "2": "1X2_2"}[sel])
            if not odds or prob * odds < 1.05:
                continue
            sh, sa, sport = lst[0][1], lst[0][2], lst[0][3]
            bets.append(
                {
                    "match_id": mid,
                    "sport": sport,
                    "sel": sel,
                    "prob": round(prob, 4),
                    "odds": odds,
                    "result": settle_1x2(sh, sa) == sel,
                }
            )
        consensus_bets[f"avg_p>={thr}"] = summarize(bets)

    # Top selections from main prediction
    label_rank_real = {
        k: summarize(v) for k, v in by_label_real.items() if len(v) >= 15
    }
    label_rank_assume = {
        k: summarize(v) for k, v in by_label_assume.items() if len(v) >= 15
    }

    report = {
        "source": str(DB),
        "universe": {
            "matches_settled": len(matches),
            "matches_with_prediction": sum(1 for m in matches if normalize_pred(m["prediction"])),
            "odds_matches": len(odds_idx),
            "sub_strategies": subs,
            "main_strategies": strategies,
            "unknown_predictions": dict(sorted(unknown.items(), key=lambda x: -x[1])[:20]),
        },
        "main_prediction": {
            "real_odds_only": summarize(main_bets_real),
            "with_assumed_1x2_dc": summarize(main_bets_assume),
            "by_selection_real_odds": dict(
                sorted(label_rank_real.items(), key=lambda x: -(x[1]["roi_pct"] or -999))
            ),
            "by_selection_assumed": dict(
                sorted(label_rank_assume.items(), key=lambda x: -(x[1]["roi_pct"] or -999))
            ),
            "by_sport_real": {k: summarize(v) for k, v in by_sport.items()},
        },
        "strategy_predictions_table": {
            name: summarize(bets) for name, bets in sp_by_strat.items()
        },
        "substrategy_value_bets": {
            "top_30_by_roi": ranked_subs[:30],
            "all_configs": sub_backtests,
            "consensus_avg_subs": consensus_bets,
        },
        "assumptions": {
            "unit_stake": 1.0,
            "assumed_odds_when_missing": ASSUMED_ODDS,
            "edge_definition": "model_prob * decimal_odds",
            "note": (
                "matches.profit в БД пустой (все 0) — ROI посчитан ретроспективно. "
                "real_odds_only использует только найденные котировки из таблицы odds."
            ),
        },
    }

    # Best overall recommendation
    best = ranked_subs[0] if ranked_subs else None
    best_main = None
    if label_rank_real:
        best_main = max(label_rank_real.items(), key=lambda x: (x[1]["roi_pct"] or -999, x[1]["bets"]))
    report["verdict"] = {
        "best_substrategy_config": best,
        "best_main_selection_real_odds": (
            {"selection": best_main[0], **best_main[1]} if best_main else None
        ),
        "main_prediction_overall_real": report["main_prediction"]["real_odds_only"],
        "main_prediction_overall_assumed": report["main_prediction"]["with_assumed_1x2_dc"],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary (ASCII-safe-ish)
    v = report["verdict"]
    print("Settled matches:", len(matches))
    print("Main prediction REAL odds:", report["main_prediction"]["real_odds_only"])
    print("Main prediction ASSUMED:", report["main_prediction"]["with_assumed_1x2_dc"])
    print("By selection (real):")
    for k, s in list(report["main_prediction"]["by_selection_real_odds"].items())[:10]:
        print(f"  {k}: n={s['bets']} WR={s['winrate_pct']} ROI={s['roi_pct']} profit={s['profit']}")
    print("Top substrategy configs:")
    for row in ranked_subs[:12]:
        print(
            f"  {row['strategy']} | {row['config']}: n={row['bets']} "
            f"WR={row['winrate_pct']} ROI={row['roi_pct']} profit={row['profit']}"
        )
    print("Consensus:")
    for k, s in consensus_bets.items():
        print(f"  {k}: {s}")
    print("strategy_predictions:")
    for k, s in report["strategy_predictions_table"].items():
        print(f"  {k}: {s}")
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
