"""Migrate odds table to canonical market_name (1X2_1, OVER 2.5, …)."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from odds_normalize import (  # noqa: E402
    canonicalize_market,
    expand_wide_1x2_row,
    split_canonical,
    to_float,
)


def row_to_pairs(row: sqlite3.Row) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    # Wide legacy columns
    wide = expand_wide_1x2_row(dict(row))
    if wide:
        pairs.extend(wide)

    ov = to_float(row["odds_value"])
    if ov and ov > 1:
        canon = canonicalize_market(
            row["market_name"],
            outcome=row["outcome"],
            side=row["side"],
            line_value=row["line_value"],
        )
        if canon and canon.upper() not in ("1X2", "1x2".upper(), "OVER", "UNDER", "HANDICAP", "BTTS", "DC"):
            pairs.append((canon, ov))
        elif canon:
            pairs.append((canon, ov))
    return pairs


def main() -> int:
    conn = sqlite3.connect("matches.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM odds").fetchall()
    print(f"source rows: {len(rows)}")

    best: dict[tuple[str, str], float] = {}
    skipped = 0
    for r in rows:
        mid = r["match_id"]
        pairs = row_to_pairs(r)
        if not pairs:
            skipped += 1
            continue
        for market, odds in pairs:
            key = (mid, market)
            if key not in best or odds > best[key]:
                best[key] = odds

    print(f"canonical pairs: {len(best)} (skipped source rows without usable odds: {skipped})")

    batch = []
    for (mid, market), odds in best.items():
        meta = split_canonical(market)
        batch.append(
            (
                mid,
                None,  # home_win_odds
                None,  # draw_odds
                None,  # away_win_odds
                None,  # odds_1x
                None,  # odds_12
                None,  # odds_2x
                market,
                meta.get("line_value"),
                None,  # predicted_value
                meta.get("outcome"),
                meta.get("side"),
                odds,
            )
        )

    conn.execute("DELETE FROM odds")
    conn.executemany(
        """
        INSERT INTO odds (
            match_id, home_win_odds, draw_odds, away_win_odds,
            odds_1x, odds_12, odds_2x,
            market_name, line_value, predicted_value, outcome, side, odds_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )
    conn.commit()

    samples = list(
        conn.execute(
            """
            SELECT market_name, COUNT(*) c, COUNT(DISTINCT match_id) m
            FROM odds GROUP BY market_name ORDER BY c DESC LIMIT 20
            """
        )
    )
    print("top markets after migrate:")
    for m, c, n in samples:
        print(f"  {m}: rows={c} matches={n}")

    for key in ("1X2_1", "1X2_X", "1X2_2"):
        n = conn.execute(
            "SELECT COUNT(DISTINCT match_id) FROM odds WHERE market_name=?", (key,)
        ).fetchone()[0]
        print(f"matches with {key}: {n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
