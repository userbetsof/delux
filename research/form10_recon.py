"""Разведка данных для исследования XGBoost с одним признаком — форма за 10 матчей."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
DB = ROOT / "matches.db"


def main() -> int:
    print(f"python={sys.version.split()[0]} exe={sys.executable}")
    print(f"db={DB} exists={DB.exists()}")
    if not DB.exists():
        return 1
    print(f"db_size_mb={DB.stat().st_size / 1024 / 1024:.1f}")

    for name in ("xgboost", "sklearn", "pandas", "numpy", "catboost", "mlflow", "joblib"):
        try:
            module = __import__(name)
            print(f"pkg {name}: {getattr(module, '__version__', '?')}")
        except Exception as exc:  # noqa: BLE001
            print(f"pkg {name}: MISSING ({type(exc).__name__})")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]
    print(f"\ntables({len(tables)}): {tables}")

    for table in ("matches", "teams", "odds", "match_snapshot"):
        if table not in tables:
            print(f"\n[{table}] ABSENT")
            continue
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        rows = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"\n[{table}] rows={rows}")
        print(f"  cols={cols}")

    if "matches" in tables:
        print("\n--- matches ---")
        for sql, label in (
            ("SELECT COUNT(*) FROM matches", "total"),
            ("SELECT COUNT(*) FROM matches WHERE match_status='Завершен'", "finished"),
            ("SELECT COUNT(*) FROM matches WHERE score_home IS NOT NULL AND score_away IS NOT NULL", "with_score"),
            ("SELECT COUNT(*) FROM matches WHERE sport IS NOT NULL", "with_sport"),
            ("SELECT COUNT(DISTINCT home_team_id) FROM matches", "distinct_home_teams"),
            ("SELECT COUNT(DISTINCT league_id) FROM matches", "distinct_leagues"),
        ):
            try:
                print(f"  {label}: {cur.execute(sql).fetchone()[0]}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {label}: ERR {exc}")

        try:
            print("  sport distribution:")
            for sid, n in cur.execute(
                "SELECT sport, COUNT(*) FROM matches GROUP BY sport ORDER BY 2 DESC"
            ):
                print(f"    sport={sid!r} n={n}")
        except Exception as exc:  # noqa: BLE001
            print(f"  sport dist ERR {exc}")

        try:
            print("  status distribution:")
            for st, n in cur.execute(
                "SELECT match_status, COUNT(*) FROM matches GROUP BY match_status ORDER BY 2 DESC"
            ):
                print(f"    {st!r} n={n}")
        except Exception as exc:  # noqa: BLE001
            print(f"  status dist ERR {exc}")

        try:
            lo, hi = cur.execute(
                "SELECT MIN(match_date), MAX(match_date) FROM matches"
            ).fetchone()
            print(f"  date range: {lo} .. {hi}")
        except Exception as exc:  # noqa: BLE001
            print(f"  date range ERR {exc}")

        try:
            print("  matches per year:")
            for year, n in cur.execute(
                "SELECT substr(match_date,1,4) y, COUNT(*) FROM matches "
                "WHERE match_date IS NOT NULL GROUP BY y ORDER BY y"
            ):
                print(f"    {year}: {n}")
        except Exception as exc:  # noqa: BLE001
            print(f"  per-year ERR {exc}")

        try:
            print("  top leagues:")
            for lid, n in cur.execute(
                "SELECT league_id, COUNT(*) FROM matches GROUP BY league_id ORDER BY 2 DESC LIMIT 15"
            ):
                print(f"    league={lid!r} n={n}")
        except Exception as exc:  # noqa: BLE001
            print(f"  leagues ERR {exc}")

        try:
            print("  sample finished rows:")
            for row in cur.execute(
                "SELECT match_id, match_date, sport, league_id, home_team_id, away_team_id, "
                "score_home, score_away, match_status FROM matches "
                "WHERE match_status='Завершен' ORDER BY match_date DESC LIMIT 5"
            ):
                print(f"    {row}")
        except Exception as exc:  # noqa: BLE001
            print(f"  sample ERR {exc}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
