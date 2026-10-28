"""E2E-проверка проставления кф при сохранении анализа (на копии БД)."""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

src = ROOT / "matches.db"
dst = ROOT / "research" / "_test_odds.db"
for suffix in ("", "-wal", "-shm"):
    p = Path(str(dst) + suffix)
    if p.exists():
        p.unlink()
shutil.copy(src, dst)

os.environ["DATABASE_PATH"] = str(dst)

from db import get_db_connection  # noqa: E402
from match_analysis import save_analysis_to_db  # noqa: E402

MATCH_ID = "KdLPRx82"

# Обнулим кф, чтобы проверить именно автопроставление.
with get_db_connection() as conn:
    conn.execute("UPDATE strategy_predictions SET odds = NULL WHERE match_id = ?", (MATCH_ID,))
    conn.commit()

results = {
    "league": "АНГЛИЯ / Премьер-лига",
    "home": "Арсенал",
    "away": "Челси",
    "match_date": "2025.10.01 20:00",
    "prediction_ntb": "ТБ 2,5",
    "prediction_betalone": "1X",
    "prediction_sniper": "ТБ 1,5",
    "match_status": 3,
}

save_analysis_to_db(MATCH_ID, 1, results, odds_markets=[], partial=False)

with get_db_connection() as conn:
    for r in conn.execute(
        "SELECT strategy_id, prediction, odds FROM strategy_predictions WHERE match_id = ? ORDER BY strategy_id",
        (MATCH_ID,),
    ):
        print(f"#{r['strategy_id']} {r['prediction']!r} @ {r['odds']}")

print("\n-- ожидаем: #1 ТБ 2,5 @ 1.79, #2 1X @ ?, #3 ТБ 1,5 @ 1.24")
