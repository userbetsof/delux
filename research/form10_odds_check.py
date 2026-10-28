"""Проверка качества кэ-одов 1X2 и пригодности для ROI."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(r"C:\papki\work\bets\delux\matches.db")


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    odds = pd.read_sql_query(
        """
        SELECT id, match_id, market_name, outcome, side, line_value, odds_value,
               home_win_odds, draw_odds, away_win_odds, odds_1x, odds_12, odds_2x
        FROM odds
        WHERE market_name IN ('1X2_1','1X2_X','1X2_2')
        """,
        con,
    )
    matches = pd.read_sql_query(
        """
        SELECT match_id, sport, score_home, score_away, match_date
        FROM matches
        WHERE match_status='Завершен' AND score_home IS NOT NULL AND score_away IS NOT NULL
        """,
        con,
    )
    con.close()

    print(f"строк 1X2 в odds: {len(odds)} ; матчей: {odds['match_id'].nunique()}")

    print("\n=== сколько строк на (match_id, market) ===")
    per = odds.groupby(["match_id", "market_name"]).size()
    print(per.value_counts().sort_index().to_string())

    print("\n=== пример матча со многими строками ===")
    busy = per.idxmax()[0]
    print(f"match_id={busy}")
    print(odds[odds["match_id"] == busy].head(12).to_string())

    print("\n=== коды 1X2 vs legacy-колонки home_win_odds/draw_odds/away_win_odds ===")
    legacy = odds[["odds_value", "home_win_odds", "draw_odds", "away_win_odds",
                   "odds_1x", "odds_12", "odds_2x", "market_name"]]
    print(legacy.head(10).to_string())
    print("доля непустых legacy-колонок:")
    print(legacy[["home_win_odds", "draw_odds", "away_win_odds", "odds_1x", "odds_12", "odds_2x"]]
          .notna().mean().to_string())

    print("\n=== range odds_value по рынкам ===")
    print(odds.groupby("market_name")["odds_value"].describe().to_string())

    print("\n=== пересечение с матчами по видам спорта ===")
    merged = odds.merge(matches[["match_id", "sport", "score_home", "score_away"]], on="match_id", how="inner")
    print(merged.groupby(["sport", "market_name"]).size().to_string())

    pivot = merged.pivot_table(index="match_id", columns="market_name",
                               values="odds_value", aggfunc="max")
    print(f"\nматчей с полным набором 1X2: {pivot.notna().all(axis=1).sum()} из {len(pivot)}")
    print("пропуски по рынкам:")
    print(pivot.isna().sum().to_string())

    full = pivot.dropna()
    if len(full):
        inv = 1.0 / full[["1X2_1", "1X2_X", "1X2_2"]].to_numpy(dtype=float)
        over = inv.sum(axis=1)
        print(f"\noverround (сумма 1/кэф): min={over.min():.3f} медиана={np.median(over):.3f} max={over.max():.3f}")
        norm = inv / over[:, None]
        meta = full.join(matches.set_index("match_id")[["sport", "score_home", "score_away"]])
        actual = np.where(meta["score_home"] > meta["score_away"], 1,
                          np.where(meta["score_home"] < meta["score_away"], 2, 0))
        print("\nсравнение средней подразумеваемой вероятности с частотой (по видам спорта):")
        for sport in sorted(meta["sport"].unique()):
            mask = (meta["sport"] == sport).to_numpy()
            if mask.sum() < 20:
                continue
            p = norm[mask]
            a = actual[mask]
            acc = (np.asarray([0, 1, 2])[p.argmax(axis=1)] == a).mean()
            print(f"  sport={sport} n={mask.sum()}: implied 1/X/2 = "
                  f"{p[:,0].mean():.3f}/{p[:,1].mean():.3f}/{p[:,2].mean():.3f} | "
                  f"факт 1/X/2 = {(a==1).mean():.3f}/{(a==0).mean():.3f}/{(a==2).mean():.3f} | "
                  f"точность фаворита рынка = {acc:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
